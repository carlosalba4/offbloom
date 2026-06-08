# CLAUDE.md — Contrato para agentes de este proyecto

Léelo antes de actuar. Aplica a la sesión principal de Claude Code y a todos los
subagentes de `.claude/agents/`.

## 1. Qué construimos

Un **coach de bienestar digital, agéntico y privacy-first**. Filosofía:
*"sustituir, no prohibir"* — en vez de bloquear apps, el coach analiza los
patrones de uso de la persona y le propone un plan semanal y actividades offline
personalizadas. No es un proyecto académico: solo hacemos lo que aporta valor
profesional o de producto.

## 2. Stack

- Python 3.12 + **uv** (entorno y dependencias).
- **FastAPI + Pydantic v2** (backend y validación).
- **LangGraph** (orquestación del coach multiagente).
- **chromadb** + embeddings **bge-m3** multilingües (RAG).
- LLM **agnóstico**: Ollama (local/privacidad) o API (demo pública), vía `LLM_PROVIDER`.
- **Langfuse** (trazas de agentes) · **DeepEval** (evals de comportamiento).
- **Next.js + Tailwind + shadcn/ui** (frontend, en `frontend/`).
- **Docker** (empaquetado) · **GitHub Actions** (CI).

## 3. Arquitectura (respeta las capas)

```
src/coach/
  config.py     # settings desde env (nada hardcodeado)
  llm/          # capa AGNÓSTICA: get_chat_model() / get_embeddings()
  graph/        # el coach en LangGraph: state.py, graph.py, nodes/
  rag/          # chromadb + retriever
  main.py       # FastAPI; los handlers son finos
```

Regla de oro: **nunca importes un modelo concreto.** Usa siempre
`coach.llm.get_chat_model()`. La presentación (FastAPI/Next) no mete lógica en
`graph/`; el dominio del coach no sabe nada del framework web.

## 4. El equipo de agentes

La **sesión principal orquesta**: descompone el trabajo y delega en los
subagentes de `.claude/agents/`. No hay un agente "orquestador" separado —ese
papel lo hace la sesión principal (Opus 4.8)—. Subagentes disponibles:

| Subagente        | Para qué                                              |
| ---------------- | ----------------------------------------------------- |
| `architect`      | Diseño, fronteras de módulos, ADRs                    |
| `agent-engineer` | El coach en LangGraph (núcleo del producto)           |
| `backend-dev`    | FastAPI, schemas, capa LLM agnóstica                  |
| `rag-engineer`   | chromadb, embeddings, ingesta, retriever              |
| `frontend-dev`   | Next.js + Tailwind + shadcn/ui                        |
| `eval-engineer`  | DeepEval + Langfuse (calidad del coach)               |
| `tester`         | pytest (tras cada módulo)                             |
| `qa-reviewer`    | Revisión vs arquitectura/SOLID/seguridad (proactivo)  |
| `devops`         | Docker, CI, despliegue                                |

## 5. Routing por modelo y esfuerzo (gestión de cuota)

Trabajamos con Opus 4.8 en Pro: la cuota es compartida y semanal, así que
ruteamos por esfuerzo (`/effort`), no por persona.

- **Esfuerzo alto / Opus**: arquitectura, cableado del coach LangGraph, diseño de
  evals, debugging difícil, revisión QA.
- **Medio / Sonnet**: implementación de endpoints, RAG, frontend, devops.
- **Bajo**: boilerplate, tests rutinarios, docs.

Reserva el gasto fuerte para cuando lanzas subagentes en paralelo.

## 6. Flujo de trabajo (supervisión humana)

1. El agente **propone un plan** y espera aprobación.
2. Se ejecuta el plan aprobado.
3. Se verifica el resultado (typecheck/lint/tests) antes de commit.

Si una tarea es ambigua, **pregunta**; no asumas. Si una herramienta falla,
reporta el error textual y reintenta con otra estrategia; no parchees a ciegas.

## 7. Convenciones

- TypeScript/Python con tipado estricto; nada de tipos `Any` evitables.
- Nombres en **inglés** (variables, funciones, clases). Documentación, comentarios
  funcionales y mensajes de commit en **español**.
- Commits convencionales: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- Lint/format con **ruff**. Tests con **pytest** (estructura AAA).
- Decisiones consecuentes → un ADR numerado en `docs/decisions/`.

## 8. Calidad y seguridad (definición de "hecho")

- Tests verdes y `ruff check` limpio.
- El coach toca un dominio sensible (bienestar): **nunca** da consejo dañino de
  salud mental; ante señales de riesgo, redirige a ayuda profesional. Esto lo
  verifican las evals de `eval-engineer` y es **bloqueante**.
- Toda ejecución del grafo queda trazada en Langfuse.
- Sin secretos en el repo (usa `.env` / secrets de la plataforma).

## 9. Despliegue

La demo pública corre con `LLM_PROVIDER=api` (un contenedor remoto no alcanza el
Ollama local). El modo local/privacidad se demuestra y se documenta aparte. La
privacidad es una **capacidad de la arquitectura** (cualquiera puede self-hostar
100% local con Ollama), no una promesa sobre el demo alojado.
