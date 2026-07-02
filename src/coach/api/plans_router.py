"""Endpoint de check-in: POST /plans.

Carga el perfil persistido del usuario autenticado, invoca el grafo del coach
(sin modificarlo) y persiste el resultado como una fila Plan asociada al
usuario. Handler síncrono para que FastAPI lo despache al threadpool y no
bloquee el event loop durante la llamada (potencialmente lenta) al LLM.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from coach.api.deps import get_current_user, get_db
from coach.api.observability import langfuse_callbacks
from coach.api.schemas import PlanRequest, PlanResponse
from coach.config import settings
from coach.db.mappers import (
    coach_result_to_plan_row,
    plan_row_to_activities,
    plan_row_to_derivation,
    plan_row_to_weekly_plan,
    profile_to_domain,
)
from coach.db.models.user import User
from coach.db.repositories import PlanRepo, ProfileRepo
from coach.graph.state import CoachState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["plans"])


@router.post("", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(
    body: PlanRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanResponse:
    """Ejecuta el coach LangGraph con el perfil persistido y guarda el resultado.

    404 si el usuario no ha completado el onboarding (sin perfil). 502 si el
    grafo falla (detalle genérico, sin filtrar internos). La derivación a
    ayuda profesional es un resultado válido (sigue siendo HTTP 201).
    """
    profile_orm = ProfileRepo(db).get_by_user_id(current_user.id)
    if profile_orm is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Perfil sin onboarding")

    input_profile = profile_to_domain(profile_orm)

    # Construye el estado inicial con solo los canales de entrada.
    state: CoachState = {"profile": input_profile, "usage": body.usage}

    try:
        result: CoachState = request.app.state.graph.invoke(
            state,
            config={"callbacks": langfuse_callbacks()},
        )
    except Exception as exc:
        logger.exception("Error al invocar el grafo del coach")
        raise HTTPException(
            status_code=502,
            detail="El coach no pudo procesar la petición. Inténtalo de nuevo.",
        ) from exc

    llm_model = settings.ollama_model if settings.llm_provider == "ollama" else settings.api_model
    plan_row = coach_result_to_plan_row(
        result,
        user_id=current_user.id,
        input_profile=input_profile,
        input_usage=body.usage,
        llm_provider=settings.llm_provider,
        llm_model=llm_model,
    )
    plan_row = PlanRepo(db).create(plan_row)
    db.commit()

    return PlanResponse(
        id=plan_row.id,
        status=str(plan_row.status),
        created_at=plan_row.created_at,
        plan=plan_row_to_weekly_plan(plan_row),
        activities=plan_row_to_activities(plan_row),
        derivation=plan_row_to_derivation(plan_row),
        errors=plan_row.errors or [],
    )
