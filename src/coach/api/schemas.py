"""Modelos Pydantic v2 de request/response para los endpoints de autenticación.

Los requests usan extra="forbid" para rechazar campos desconocidos. Ningún
modelo de respuesta expone password ni password_hash.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Cuerpo de la petición de registro."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Cuerpo de la petición de login."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(max_length=128)


class RefreshRequest(BaseModel):
    """Cuerpo de la petición de renovación de tokens."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class LogoutRequest(BaseModel):
    """Cuerpo de la petición de logout."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class TokenResponse(BaseModel):
    """Par de tokens emitido tras login o refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Representación pública de un usuario (nunca incluye el hash)."""

    id: str
    email: str
    has_profile: bool


class MessageResponse(BaseModel):
    """Respuesta genérica de confirmación (p.ej. logout)."""

    detail: str
