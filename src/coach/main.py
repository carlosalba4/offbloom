"""FastAPI entrypoint. Keep route handlers thin: validate -> call graph -> return."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from coach.api.auth_router import router as auth_router
from coach.api.plans_router import router as plans_router
from coach.api.profile_router import router as profile_router
from coach.config import settings
from coach.graph.graph import build_coach_graph

logger = logging.getLogger(__name__)


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

# Permite que el frontend llame a la API con credenciales (la cookie httpOnly
# del refresh token viaja en cada petición). allow_credentials=True exige un
# origen explícito -- nunca "*" -- por eso se restringe a settings.frontend_origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(plans_router)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "llm_provider": settings.llm_provider}
