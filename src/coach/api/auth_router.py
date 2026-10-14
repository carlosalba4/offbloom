"""Endpoints de autenticación: registro, login (contraseña o Google), refresh,
logout y perfil actual.

Handlers finos: validan el body (Pydantic), delegan en AuthService y traducen
las excepciones de dominio a códigos HTTP. El commit de las mutaciones lo hace
siempre el handler, nunca el servicio (Pattern B / Decisión D4).
"""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from coach.api.cookies import (
    clear_oauth_state_cookie,
    clear_refresh_cookie,
    set_oauth_state_cookie,
    set_refresh_cookie,
)
from coach.api.deps import get_current_user, get_db, get_google_client
from coach.api.schemas import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from coach.auth.google import GoogleOAuthClient, GoogleOAuthError
from coach.auth.service import (
    AuthService,
    EmailAlreadyExists,
    GoogleAccountAlreadyLinked,
    InvalidCredentials,
    InvalidRefreshToken,
    UnverifiedGoogleEmail,
)
from coach.config import settings
from coach.db.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

# Mensaje único para credenciales inválidas: el mismo status y cuerpo tanto
# si el email no existe como si la contraseña es incorrecta (no revela
# si una cuenta existe).
_INVALID_CREDENTIALS_DETAIL = "Credenciales inválidas"

# Longitud en bytes del `state` anti-CSRF del flujo OAuth.
_OAUTH_STATE_BYTES = 32


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> UserResponse:
    """Crea una cuenta nueva. 409 si el email ya está registrado."""
    service = AuthService(db)
    try:
        user = service.register(body.email, body.password)
    except EmailAlreadyExists as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    db.commit()
    return UserResponse(id=user.id, email=user.email, has_profile=user.profile is not None)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    """Autentica y emite un access token. 401 genérico si las credenciales son inválidas.

    El refresh token se transporta en una cookie httpOnly (no viaja en el body).
    """
    service = AuthService(db)
    try:
        access_token, refresh_token = service.authenticate(body.email, body.password)
    except InvalidCredentials as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS_DETAIL
        ) from exc

    set_refresh_cookie(response, refresh_token)
    db.commit()
    return TokenResponse(access_token=access_token)


# ---------------------------------------------------------------------------
# Login con Google (OIDC, Authorization Code Flow dirigido por el backend)
# ---------------------------------------------------------------------------


def _google_error_redirect(slug: str) -> RedirectResponse:
    """Vuelve al frontend señalando por qué no se pudo completar el login.

    Se redirige en vez de responder JSON porque quien llega aquí es el
    navegador del usuario, no un cliente de la API: un 4xx crudo sería una
    página de error en blanco. Nunca se emite sesión por este camino.
    """
    query = urlencode({"error": slug})
    response = RedirectResponse(
        f"{settings.google_post_login_url}?{query}",
        status_code=status.HTTP_302_FOUND,
    )
    clear_oauth_state_cookie(response)
    return response


@router.get("/google/login", response_class=RedirectResponse, status_code=status.HTTP_302_FOUND)
def google_login(
    google: GoogleOAuthClient = Depends(get_google_client),
) -> RedirectResponse:
    """Arranca el flujo: genera el `state` anti-CSRF y manda el navegador a Google.

    El `state` viaja por partida doble —en la URL de Google y en una cookie
    httpOnly de vida corta— para que el callback pueda comprobar que la vuelta
    corresponde a una ida que iniciamos nosotros (double-submit).
    """
    state = secrets.token_urlsafe(_OAUTH_STATE_BYTES)

    # La cookie se pone sobre la propia RedirectResponse: el objeto `Response`
    # que inyecta FastAPI solo aplica cuando el handler devuelve un cuerpo
    # serializable, no cuando devuelve una respuesta ya construida.
    response = RedirectResponse(
        google.build_authorization_url(state),
        status_code=status.HTTP_302_FOUND,
    )
    set_oauth_state_cookie(response, state)
    return response


@router.get("/google/callback", response_class=RedirectResponse, status_code=status.HTTP_302_FOUND)
def google_callback(
    request: Request,
    state: str | None = Query(default=None),
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
    google: GoogleOAuthClient = Depends(get_google_client),
) -> RedirectResponse:
    """Cierra el flujo: valida el `state`, canjea el `code` y emite la sesión.

    La sesión resultante es exactamente la del login por contraseña (mismo
    access token, misma cookie httpOnly de refresh), porque ambas salen de
    `AuthService._issue_tokens`. El access token NO viaja en la URL: el
    frontend lo obtiene con el `POST /auth/refresh` de siempre.

    Un fallo de `state` responde 400 y no redirige: es un fallo de protocolo o
    un intento de CSRF, no un desenlace que el frontend deba mostrar.
    """
    expected_state = request.cookies.get(settings.cookie_oauth_state_name)
    if not state or not expected_state or not secrets.compare_digest(state, expected_state):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Parámetro `state` inválido o ausente",
        )

    # El usuario canceló en la pantalla de consentimiento (o Google rechazó).
    if error is not None:
        return _google_error_redirect(error)

    if not code:
        return _google_error_redirect("missing_code")

    try:
        identity = google.exchange_code(code)
    except GoogleOAuthError:
        return _google_error_redirect("exchange_failed")

    service = AuthService(db)
    try:
        # El access token se descarta a propósito: no puede acompañar a una
        # redirección sin acabar expuesto en la URL. El frontend lo obtiene
        # con POST /auth/refresh usando la cookie que se emite justo debajo.
        _, refresh_token = service.login_with_google(identity)
    except UnverifiedGoogleEmail:
        return _google_error_redirect("email_not_verified")
    except GoogleAccountAlreadyLinked:
        return _google_error_redirect("account_already_linked")

    db.commit()

    response = RedirectResponse(
        settings.google_post_login_url,
        status_code=status.HTTP_302_FOUND,
    )
    set_refresh_cookie(response, refresh_token)
    clear_oauth_state_cookie(response)
    return response


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    """Rota el refresh token (leído de la cookie httpOnly) y emite un nuevo access token.

    401 si la cookie no está presente, o si el token es inválido/expirado.
    """
    token = request.cookies.get(settings.cookie_refresh_name)
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Refresh token ausente")

    service = AuthService(db)
    try:
        access_token, new_refresh_token = service.refresh(token)
    except InvalidRefreshToken as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    set_refresh_cookie(response, new_refresh_token)
    db.commit()
    return TokenResponse(access_token=access_token)


@router.post("/logout", response_model=MessageResponse)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> MessageResponse:
    """Revoca el refresh token (si la cookie está presente). Siempre 200 (idempotente).

    Independientemente de si había cookie o era válida, la respuesta siempre
    borra la cookie de refresh en el cliente.
    """
    token = request.cookies.get(settings.cookie_refresh_name)
    if token is not None:
        AuthService(db).logout(token)
        db.commit()

    clear_refresh_cookie(response)
    return MessageResponse(detail="Sesión cerrada")


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Devuelve los datos públicos del usuario autenticado."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        has_profile=current_user.profile is not None,
    )
