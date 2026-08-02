"""Endpoints del dominio /plans: check-in, historial y progreso de actividades.

POST /plans carga el perfil persistido del usuario autenticado, invoca el grafo
del coach (sin modificarlo) y persiste el resultado como una fila Plan asociada
al usuario. Handler síncrono para que FastAPI lo despache al threadpool y no
bloquee el event loop durante la llamada (potencialmente lenta) al LLM.

GET /plans y GET /plans/{id} sirven el historial; el detalle enriquece cada
actividad con su progreso. PUT /plans/{id}/activities/{i}/progress marca o
desmarca una actividad.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from coach.api.deps import get_current_user, get_db
from coach.api.observability import langfuse_callbacks
from coach.api.schemas import (
    ActivityProgressRequest,
    ActivityProgressResponse,
    ActivityWithProgress,
    PlanRequest,
    PlanResponse,
    PlanSummary,
)
from coach.config import settings
from coach.db.enums import ActivityProgressStatus
from coach.db.mappers import (
    coach_result_to_plan_row,
    plan_row_to_activities,
    plan_row_to_derivation,
    plan_row_to_weekly_plan,
    profile_to_domain,
)
from coach.db.models.plan import Plan
from coach.db.models.user import User
from coach.db.repositories import ActivityProgressRepo, PlanRepo, ProfileRepo
from coach.graph.state import CoachState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["plans"])


def _plan_row_to_response(
    plan_row: Plan,
    done_by_index: dict[int, bool] | None = None,
) -> PlanResponse:
    """Construye la respuesta pública completa de un Plan a partir de su fila ORM.

    done_by_index mapea la posición de la actividad a su progreso. Si no se
    pasa (plan recién generado), todas las actividades salen con done=False.
    """
    done_by_index = done_by_index or {}
    activities = [
        ActivityWithProgress(**activity.model_dump(), done=done_by_index.get(index, False))
        for index, activity in enumerate(plan_row_to_activities(plan_row))
    ]
    return PlanResponse(
        id=plan_row.id,
        status=str(plan_row.status),
        created_at=plan_row.created_at,
        plan=plan_row_to_weekly_plan(plan_row),
        activities=activities,
        derivation=plan_row_to_derivation(plan_row),
        errors=plan_row.errors or [],
    )


def _plan_row_to_summary(plan_row: Plan) -> PlanSummary:
    """Construye la vista resumida de un Plan para el historial (GET /plans).

    El foco solo existe cuando el plan es GENERATED; en DERIVED no hay
    weekly_plan y `focus` queda en None.
    """
    focus = plan_row.plan.get("weekly_focus") if plan_row.plan else None
    return PlanSummary(
        id=plan_row.id,
        status=str(plan_row.status),
        created_at=plan_row.created_at,
        focus=focus,
    )


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

    return _plan_row_to_response(plan_row)


@router.get("", response_model=list[PlanSummary])
def list_plans(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PlanSummary]:
    """Devuelve el historial paginado de planes del usuario autenticado.

    Vista resumida (sin plan/actividades/derivación completos): solo lo
    necesario para renderizar una lista, ordenada por fecha descendente.
    """
    plan_rows = PlanRepo(db).list_by_user(current_user.id, limit=limit, offset=offset)
    return [_plan_row_to_summary(plan_row) for plan_row in plan_rows]


@router.get("/{plan_id}", response_model=PlanResponse)
def get_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanResponse:
    """Devuelve el detalle completo de un plan propio.

    404 si el plan no existe o pertenece a otro usuario (nunca 403, para no
    revelar la existencia de recursos ajenos, ADR-007).
    """
    plan_row = PlanRepo(db).get_by_id(plan_id, current_user.id)
    if plan_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Plan no encontrado")

    progress_rows = ActivityProgressRepo(db).list_by_plan(plan_id)
    done_by_index = {
        row.activity_index: row.status is ActivityProgressStatus.DONE for row in progress_rows
    }

    return _plan_row_to_response(plan_row, done_by_index)


@router.put(
    "/{plan_id}/activities/{activity_index}/progress",
    response_model=ActivityProgressResponse,
)
def set_activity_progress(
    plan_id: str,
    activity_index: int,
    body: ActivityProgressRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ActivityProgressResponse:
    """Marca o desmarca como hecha una actividad de un plan propio (idempotente).

    404 si el plan no existe o es de otro usuario (nunca 403, ADR-007), y
    también si activity_index cae fuera del array de actividades del plan.
    El progreso es binario: done=true -> DONE, done=false -> PENDING.
    """
    plan_row = PlanRepo(db).get_by_id(plan_id, current_user.id)
    if plan_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Plan no encontrado")

    activities = plan_row.activities or []
    if not 0 <= activity_index < len(activities):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="activity_index fuera de rango",
        )

    new_status = ActivityProgressStatus.DONE if body.done else ActivityProgressStatus.PENDING
    ActivityProgressRepo(db).upsert(
        plan_id=plan_id,
        user_id=current_user.id,
        activity_index=activity_index,
        status=new_status,
    )
    db.commit()

    return ActivityProgressResponse(activity_index=activity_index, done=body.done)
