"""Dependencias FastAPI compartidas: sesión de BD, usuario actual y cliente de Google."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from coach.auth.google import GoogleOAuthClient
from coach.auth.security import InvalidTokenError, decode_access_token
from coach.config import settings
from coach.db.models.user import User
from coach.db.repositories import UserRepo
from coach.db.session import get_db

__all__ = ["get_db", "get_current_user", "get_google_client"]

# auto_error=False para poder devolver nuestro propio 401 con el detalle y
# el header WWW-Authenticate uniformes, en vez del genérico de FastAPI.
bearer = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No autenticado",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Resuelve el usuario autenticado a partir del access token en el header.

    Lanza 401 si falta el header, el token es inválido/expirado, el usuario
    no existe o su cuenta está desactivada.
    """
    if credentials is None:
        raise _UNAUTHENTICATED

    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise _UNAUTHENTICATED from exc

    user = UserRepo(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise _UNAUTHENTICATED

    return user


def get_google_client() -> GoogleOAuthClient:
    """Construye el cliente OIDC de Google a partir de la configuración.

    503 si faltan las credenciales: el login con Google es opcional, así que
    la aplicación arranca sin ellas y solo falla el endpoint que las necesita.

    Se expone como dependencia (y no como import directo en el router) para
    poder sustituirla en los tests con `app.dependency_overrides`, igual que
    ya se hace con `get_db`.
    """
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El login con Google no está configurado en este entorno",
        )

    return GoogleOAuthClient(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
    )
