# Detox App

Coach de bienestar digital **agéntico** y **privacy-first**. En lugar de bloquear
apps, analiza tus patrones de uso y te propone un plan semanal y actividades
offline personalizadas — *sustituir, no prohibir*.

> Construido desde cero por un **equipo de subagentes de IA** en Claude Code
> (orquestador + especialistas). Ver `.claude/agents/` y `CLAUDE.md`.

## Stack

Python · uv · FastAPI · LangGraph · chromadb + bge-m3 · LLM agnóstico
(Ollama / API) · Langfuse · DeepEval · Next.js · Docker · GitHub Actions.

## Arquitectura

Capa de producto: un grafo LangGraph con tres nodos — **Analista** (detecta
patrones), **Planificador** (plan semanal) y **Curador** (actividades offline) —
fundamentado por RAG y servido por una API agnóstica al modelo.

## Quickstart

```bash
uv sync                      # crea el entorno e instala dependencias
cp .env.example .env         # ajusta LLM_PROVIDER, etc.
uv run uvicorn coach.main:app --reload
# -> http://localhost:8000/health
```

Con Docker:

```bash
docker compose up --build
```

Frontend: ver `frontend/README.md`.

## Dos modos

- **Local / privacidad**: `LLM_PROVIDER=ollama` (qwen3:8b + bge-m3). Los datos no
  salen de tu máquina.
- **Demo pública**: `LLM_PROVIDER=openai` (o google/anthropic). Mejor calidad.

## Documentación

- `docs/01-prd.md` — requisitos
- `docs/02-architecture.md` — arquitectura
- `docs/decisions/` — ADRs

## Demo

_TODO: enlace a la demo desplegada + GIF/vídeo._
