"""Modelos Pydantic v2 de request/response para los endpoints de autenticación.

Los requests usan extra="forbid" para rechazar campos desconocidos. Ningún
modelo de respuesta expone password ni password_hash.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from coach.graph.state import CuratedActivity, DerivationMessage, UsageData, WeeklyPlan


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


class PlanRequest(BaseModel):
    """Cuerpo de la petición de check-in a POST /plans.

    El perfil ya no viaja en cada request: se carga desde la DB a partir del
    usuario autenticado. Solo se envían los datos de uso del check-in actual.
    """

    model_config = ConfigDict(extra="forbid")

    usage: UsageData


class PlanResponse(BaseModel):
    """Respuesta pública de un Plan persistido.

    No expone columnas de auditoría (langfuse_trace_id, llm_provider,
    llm_model) ni internos de riesgo (RiskSignal): solo lo que el usuario
    necesita ver de su check-in.
    """

    id: str
    status: str
    created_at: datetime
    plan: WeeklyPlan | None = None
    activities: list[CuratedActivity] = []
    # Cuando el gate de seguridad salta, derivation viene poblado y plan/activities
    # quedan vacíos — sigue siendo HTTP 201; el cliente distingue por derivation != null.
    derivation: DerivationMessage | None = None
    errors: list[str] = []
