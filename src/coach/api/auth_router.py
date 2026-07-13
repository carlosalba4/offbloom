"""Endpoints de autenticación: registro, login, refresh, logout y perfil actual.

Handlers finos: validan el body (Pydantic), delegan en AuthService y traducen
las excepciones de dominio a códigos HTTP. El commit de las mutaciones lo hace
siempre el handler, nunca el servicio (Pattern B / Decisión D4).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from coach.api.cookies import clear_refresh_cookie, set_refresh_cookie
from coach.api.deps import get_current_user, get_db
from coach.api.schemas import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from coach.auth.service import (
    AuthService,
    EmailAlreadyExists,
    InvalidCredentials,
    InvalidRefreshToken,
)
from coach.config import settings
from coach.db.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

# Mensaje único para credenciales inválidas: el mismo status y cuerpo tanto
# si el email no existe como si la contraseña es incorrecta (no revela
# si una cuenta existe).
_INVALID_CREDENTIALS_DETAIL = "Credenciales inválidas"


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
