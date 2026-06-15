"""FastAPI entrypoint. Keep route handlers thin: validate -> call graph -> return."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from coach.config import settings
from coach.graph.graph import build_coach_graph
from coach.graph.state import (
    CuratedActivity,
    DerivationMessage,
    UsageData,
    UserProfile,
    WeeklyPlan,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Modelos de presentación (capa API — no exponen canales internos del grafo)
# ---------------------------------------------------------------------------


class CoachRequest(BaseModel):
    """Cuerpo de la petición al endpoint /coach."""

    model_config = ConfigDict(extra="forbid")

    profile: UserProfile
    usage: UsageData


class CoachResponse(BaseModel):
    """Respuesta estructurada del coach: plan, actividades y derivación si aplica."""

    plan: WeeklyPlan | None = None
    activities: list[CuratedActivity] = []
    # Cuando el gate de seguridad salta, derivation viene poblado y plan/activities
    # quedan vacíos — sigue siendo HTTP 200; el cliente distingue por derivation != null.
    derivation: DerivationMessage | None = None
    errors: list[str] = []


# ---------------------------------------------------------------------------
# Helper de observabilidad (import perezoso para no romper si langfuse falta)
# ---------------------------------------------------------------------------


def _langfuse_callbacks() -> list:
    """Devuelve [CallbackHandler] si las claves de Langfuse están configuradas.

    Usa import perezoso y captura cualquier error de import o construcción para
    degradar a lista vacía sin romper la request.
    """
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return []

    try:
        from langfuse.langchain import CallbackHandler  # noqa: PLC0415

        handler = CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        return [handler]
    except Exception as exc:  # noqa: BLE001
        # Langfuse no disponible o mal configurado — el coach sigue sin trazas.
        logger.warning("Langfuse no disponible, trazas desactivadas: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Ciclo de vida: el grafo se compila UNA vez al arrancar
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Compila el grafo del coach en el arranque y lo almacena en app.state."""
    logger.info("Compilando el grafo del coach...")
    app.state.graph = build_coach_graph()
    logger.info("Grafo listo.")
    yield
    # Teardown: nada que limpiar por ahora.


app = FastAPI(title="Wellbeing Coach API", version="0.1.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "llm_provider": settings.llm_provider}


@app.post("/coach", response_model=CoachResponse)
def coach(req: CoachRequest, request: Request) -> CoachResponse:
    """Ejecuta el coach LangGraph y devuelve el plan + actividades.

    El handler es síncrono para que FastAPI lo despache al threadpool y no
    bloquee el event loop durante la llamada (potencialmente lenta) al LLM.
    La derivación a ayuda profesional es un resultado válido (HTTP 200).
    """
    from coach.graph.state import CoachState  # noqa: PLC0415

    # Construye el estado inicial con solo los canales de entrada.
    state: CoachState = {"profile": req.profile, "usage": req.usage}

    try:
        result: CoachState = request.app.state.graph.invoke(
            state,
            config={"callbacks": _langfuse_callbacks()},
        )
    except Exception as exc:
        logger.exception("Error al invocar el grafo del coach")
        raise HTTPException(
            status_code=502,
            detail="El coach no pudo procesar la petición. Inténtalo de nuevo.",
        ) from exc

    return CoachResponse(
        plan=result.get("plan"),
        activities=result.get("activities", []),
        derivation=result.get("derivation"),
        errors=result.get("errors", []),
    )
