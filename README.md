# OffBloom

An **agentic**, **privacy-first** digital wellbeing coach. Instead of blocking apps, it analyses your usage patterns and proposes a weekly plan with personalised offline activities — *substitute, don't forbid*.

Built on a LangGraph agent grounded by RAG, served through a model-agnostic FastAPI backend, with a Next.js frontend. Runs fully local (Ollama) or against hosted LLM providers.

---

## Stack

| Layer | Technologies |
| --- | --- |
| Agent | LangGraph, ChromaDB + bge-m3 (RAG), model-agnostic LLM layer (Ollama / OpenAI / Google / Anthropic) |
| Backend | Python, FastAPI, SQLAlchemy + Alembic, SQLite, uv |
| Auth | Argon2 password hashing, JWT access tokens, rotating hashed refresh tokens in httpOnly cookies |
| Frontend | Next.js, TypeScript |
| Quality | pytest (206 tests), Ruff, DeepEval safety gate, LLM-as-judge groundedness eval |
| Ops | Docker, Docker Compose, GitHub Actions CI, Langfuse tracing |

## Architecture

The product layer is a **LangGraph graph with three nodes**:

- **Analyst** — detects usage patterns.
- **Planner** — produces the weekly plan.
- **Curator** — selects offline activities, grounded by RAG over a curated corpus.

The graph is served by an API that is agnostic to the underlying model, so the same code runs against a local model or a hosted provider with a single environment variable.

**Enforced boundaries:** `graph/` and `rag/` are never imported from `api/`, `db/` or `auth/`. The whole test suite runs in CI without requiring Ollama.

### Authentication

- Email + password registration and login, with Argon2 hashing.
- Short-lived JWT access tokens plus rotating refresh tokens, stored hashed and delivered in httpOnly cookies.
- Account deletion (`DELETE /me`) with password reauthentication and atomic cascade across all user-owned tables.
- Google sign-in (OIDC authorization code flow, backend-driven) — backend complete and tested on the `feat/google-oauth` branch; frontend integration pending.

Every non-obvious decision is written up as an ADR in `docs/decisions/`.

## Quickstart

```bash
uv sync                            # create the environment and install dependencies
cp .env.example .env               # set LLM_PROVIDER and the keys you need
uv run alembic upgrade head        # apply database migrations
uv run uvicorn coach.main:app --reload
# -> http://localhost:8000/health
```

With Docker:

```bash
docker compose up --build
```

Frontend: see `frontend/README.md`.

## Running modes

- **Local / privacy** — `LLM_PROVIDER=ollama` (qwen3:8b + bge-m3). No data leaves your machine.
- **Hosted** — `LLM_PROVIDER=openai` (or `google` / `anthropic`). Higher quality output.

## Tests and quality

```bash
uv run pytest                      # 206 tests
uv run ruff check .
uv run ruff format --check .
```

Beyond unit and integration tests, the evaluation layer includes a **DeepEval safety gate** and an **LLM-as-judge groundedness evaluation**, both documented in ADR-004 and ADR-005 and wired into CI.

## Documentation

- `docs/01-prd.md` — product requirements
- `docs/02-architecture.md` — architecture
- `docs/decisions/` — architecture decision records (ADR-001 to ADR-011)
- `docs/known-issues.md` — known limitations and deferred fixes

## Development approach

The project was built through an agentic development workflow designed for this repository: a set of specialised Claude Code subagents (architect, backend, frontend, RAG, evaluation, QA) operating under explicit review gates. The architectural decisions, boundaries and trade-offs are recorded in `docs/decisions/` and in `CLAUDE.md`.

## Roadmap

- Google sign-in frontend integration
- Cloud deployment (AWS) with PostgreSQL
