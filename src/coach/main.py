"""FastAPI entrypoint. Keep route handlers thin: validate -> call graph -> return."""
from __future__ import annotations

from fastapi import FastAPI

from coach.config import settings

app = FastAPI(title="Wellbeing Coach API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "llm_provider": settings.llm_provider}


# TODO(backend-dev): add POST /coach that runs the LangGraph coach and
# returns the structured plan + activities.
