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


class TokenResponse(BaseModel):
    """Access token emitido tras login o refresh.

    El refresh token ya no viaja en el body: se transporta en una cookie
    httpOnly (ver `coach.api.cookies`), invisible a JavaScript.
    """

    access_token: str
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


class PlanSummary(BaseModel):
    """Vista resumida de un Plan para el historial (GET /plans).

    No incluye el plan completo (WeeklyPlan/actividades/derivación): solo lo
    justo para renderizar una fila de lista. `focus` es el weekly_focus del
    plan generado; None cuando status=DERIVED (no hubo plan, solo derivación,
    que el cliente distingue por status).
    """

    id: str
    status: str
    created_at: datetime
    focus: str | None = None
