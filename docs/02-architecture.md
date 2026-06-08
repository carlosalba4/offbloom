# Arquitectura — Wellbeing Coach

> Diseño del coach multiagente en LangGraph: capas, contrato del estado compartido,
> flujo Analista → Planificador → Curador con gate de seguridad, y dónde entra el
> RAG. Las decisiones consecuentes se registran en `docs/decisions/`.

## 1. Capas

```
src/coach/
  config.py     # settings desde env (nada hardcodeado)
  llm/          # capa AGNÓSTICA: get_chat_model() / get_embeddings()
  graph/        # el coach en LangGraph: state.py, graph.py, nodes/
  rag/          # chromadb + retriever (bge-m3)
  main.py       # FastAPI; handlers finos
```

Regla de oro: **nadie importa un modelo concreto** (siempre vía `coach.llm`). La
presentación (FastAPI/Next) no mete lógica en `graph/`; el dominio del coach no
conoce el framework web. Ver ADR-001.

## 2. Contrato del estado compartido — `CoachState` (la "carpeta")

`CoachState` es un `TypedDict(total=False)` (canales de LangGraph) cuyos campos son
**modelos Pydantic v2**, de modo que cada nodo valida en su frontera y no circulan
tipos `Any`. Ver ADR-003.

| Campo        | Tipo (modelo Pydantic)                                                       | Lo escribe          | Lo leen                         |
| ------------ | --------------------------------------------------------------------------- | ------------------- | ------------------------------- |
| `profile`    | `UserProfile` (goals, interests, constraints: tiempo/energía/lugar/social, lang) | entrada (onboarding) | Analista, Planificador, Curador |
| `usage`      | `UsageData` (tiempo por categoría, franjas pico p. ej. nocturna, triggers autoreportados) | entrada             | Analista                        |
| `analysis`   | `Analysis` (patrones, triggers, *necesidad que cubría* cada uso)             | Analista            | Planificador, Curador           |
| `risk`       | `RiskSignal` (`flag: bool`, `reason`, `severity`)                            | Analista            | arista condicional (gate)       |
| `retrieved`  | `list[RetrievedChunk]` (texto + `id/categoria/fuente` para citar)           | Planificador (y Curador) | Planificador, Curador           |
| `plan`       | `WeeklyPlan` (foco semanal, intenciones, *swaps*, citas de `fuente`)        | Planificador        | Curador, salida                 |
| `activities` | `list[CuratedActivity]` (3 actividades + razón + por-qué-encaja)            | Curador             | salida                          |
| `derivation` | `DerivationMessage \| None` (mensaje empático + tipo de recurso, sin teléfonos) | Derivación          | salida                          |
| `errors`     | `list[str]` (opcional, degradación controlada)                              | cualquiera          | salida                          |

Cada nodo produce su salida estructurada con
`get_chat_model().with_structured_output(<Modelo>)`. La traza (Langfuse) viaja por
*callbacks* inyectados desde `main.py`, **no** dentro del estado.

## 3. Flujo del grafo y dónde entra el RAG

```
            ┌─────────────┐
  entrada → │  Analista   │  lee profile+usage → Analysis + RiskSignal   (SIN RAG)
            └──────┬──────┘
                   │  arista condicional sobre risk.flag
        risk=True  │            │  risk=False
        ┌──────────▼─────┐      ▼
        │   Derivación   │   ┌───────────────┐
        │ (empático,     │   │ Planificador  │  ← RAG #1: corpus de conocimiento (.md)
        │  sin teléfonos)│   │  WeeklyPlan   │     groundedness + citas de `fuente`
        └──────┬─────────┘   └───────┬───────┘
               │                     ▼
               │             ┌───────────────┐
               │             │   Curador     │  ← RAG #2: catálogo `actividades.jsonl`
               │             │ 3 actividades │     filtro por contexto + match `reemplaza`
               │             └───────┬───────┘
               ▼                     ▼
              END                   END
```

- **Analista** — **no usa RAG**: analiza los datos de la propia persona
  (`profile` + `usage`). Emite `Analysis` (patrones, triggers, necesidad que cubría
  cada uso) y `RiskSignal`.
- **Gate de seguridad** — arista condicional sobre `risk.flag`. Si hay riesgo →
  **Derivación**, que responde con empatía y apunta a recursos mantenidos y
  adecuados a la región (sin números fijos, sin consejo clínico), y se **saltan**
  Planificador y Curador. Comportamiento anclado en `08-seguridad-y-limites.md`.
- **Planificador** — **RAG #1**: recuperación semántica sobre la colección de
  **conocimiento** (`.md` troceados por sección) para fundamentar el plan semanal y
  citar la `fuente` (soporta la eval de *groundedness*).
- **Curador** — **RAG #2**: sobre la colección de **actividades**
  (`actividades.jsonl`), recuperación + filtro por metadatos del contexto de la
  persona (`duracion_min`, `energia`, `lugar`, `social`, `momento`) casando el campo
  `reemplaza` con los *triggers* que identificó el Analista. Es el diferenciador del
  producto ("sustituir, no prohibir").

## 4. RAG — dos colecciones en Chroma

- **`knowledge`** — documentos `.md` del corpus, *chunking* por encabezado;
  metadatos `id/categoria/tags/lang/fuente` (la `fuente` permite citar procedencia).
- **`activities`** — una línea de `actividades.jsonl` = un documento; se embebe
  `descripcion` y el resto de campos se guardan como metadatos **filtrables**.

Embeddings **bge-m3** multilingüe: el corpus está en español pero la recuperación
funciona cross-lingüe (también para usuarias en inglés). El retriever de `rag/`
expone ambas colecciones a los nodos. Almacenamiento: Chroma **embebido** (ADR-002).

## 5. Nota arquitectónica abierta (embeddings en el perfil `api`)

`get_embeddings()` hoy está atada a Ollama. En el perfil `LLM_PROVIDER=api` (demo
alojado, CLAUDE.md §9) el contenedor remoto **no** alcanza el Ollama local. Habrá
que resolver con una de dos vías: (a) **rutear los embeddings por proveedor** igual
que el chat model, o (b) **precomputar/empaquetar el store de Chroma en build** y
usar un embedder cloud solo para embeber la *query* en runtime. Queda como item de
seguimiento; se documenta en ADR-001 y ADR-002 (no se resuelve en el diseño).

## 6. Observabilidad

Langfuse traza cada ejecución del grafo mediante un *callback handler* pasado en la
invocación desde `main.py`, fuera del dominio del coach.
