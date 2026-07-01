"""Endpoints de autenticación: registro, login, refresh, logout y perfil actual.

Handlers finos: validan el body (Pydantic), delegan en AuthService y traducen
las excepciones de dominio a códigos HTTP. El commit de las mutaciones lo hace
siempre el handler, nunca el servicio (Pattern B / Decisión D4).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from coach.api.deps import get_current_user, get_db
from coach.api.schemas import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
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
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Autentica y emite un par de tokens. 401 genérico si las credenciales son inválidas."""
    service = AuthService(db)
    try:
        access_token, refresh_token = service.authenticate(body.email, body.password)
    except InvalidCredentials as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS_DETAIL
        ) from exc

    db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Rota el refresh token y emite un nuevo par. 401 si es inválido/expirado."""
    service = AuthService(db)
    try:
        access_token, refresh_token = service.refresh(body.refresh_token)
    except InvalidRefreshToken as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", response_model=MessageResponse)
def logout(body: LogoutRequest, db: Session = Depends(get_db)) -> MessageResponse:
    """Revoca el refresh token. Siempre 200 (operación idempotente)."""
    service = AuthService(db)
    service.logout(body.refresh_token)
    db.commit()
    return MessageResponse(detail="Sesión cerrada")


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Devuelve los datos públicos del usuario autenticado."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        has_profile=current_user.profile is not None,
    )
