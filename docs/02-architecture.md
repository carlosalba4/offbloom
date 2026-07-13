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

## 7. Capa de persistencia (`db/`)

La expansión a app (cuentas, historial, progreso) añade tres capas **alrededor** del
coach, sin tocar el núcleo de §1–§6. Regla de oro extendida: **`graph/` y `rag/` no
importan `db/`, `auth/` ni `api/`**. El dominio Pydantic de `graph/state.py` es la
fuente de verdad de las formas; la persistencia las **guarda**, no las redefine. El
único puente ORM↔dominio son **mappers explícitos** en `db/mappers.py`.

```
src/coach/
  config.py
  llm/            # capa AGNÓSTICA (sin cambios)
  graph/          # el coach (sin cambios; no conoce db/auth/api)
  rag/            # chromadb + retriever (sin cambios)
  db/             # PERSISTENCIA
    base.py         # DeclarativeBase
    engine.py       # create_engine(database_url)
    session.py      # get_db dependency (generador SYNC)
    models/         # user, profile, plan, progress, refresh_token (ORM)
    repositories.py # UserRepo/ProfileRepo/PlanRepo/ProgressRepo (queries + ownership)
    mappers.py      # ÚNICO puente ORM <-> dominio Pydantic
  auth/           # AUTENTICACIÓN
  api/            # PRESENTACIÓN (routers)
  main.py         # solo include_router + lifespan (grafo en app.state)
```

Diagrama de dependencias (las flechas indican "importa a"):

```
                 ┌─────────────────────────────┐
                 │            api/             │  (presentación)
                 └───┬────────┬────────┬───────┘
                     │        │        │
          ┌──────────▼──┐  ┌──▼────┐  ┌▼──────────┐
          │    auth/    │  │  db/  │  │   graph/  │ (vía app.state.graph)
          └──────┬──────┘  └───┬───┘  └─────┬─────┘
                 │             │            │
                 └──────► db/ ◄┘            ▼
                                          rag/  (lo usa graph/, no api/)

  graph/ y rag/ NO importan db/, auth/ ni api/  ← frontera bloqueante
  db/ NO importa graph/ salvo los modelos Pydantic del dominio (solo lectura de forma)
```

**SQLAlchemy 2.0 síncrono.** Coherente con los handlers `def` que FastAPI despacha al
threadpool y con `graph.invoke()` bloqueante (no se gana nada con async en este MVP, y
sí se evita propagar `async`/`await` por toda la capa). `db/session.py` expone
`get_db()` como **generador síncrono** que abre y cierra una sesión **por request**.

**SQLite en desarrollo, PostgreSQL sin reescritura.** `database_url` por defecto
`sqlite:///./offbloom.db`. La portabilidad se diseña desde el inicio (ver ADR-006):
columnas **JSON** (variante **JSONB** en Postgres), UUID como `String(36)`/GUID
portable (no el tipo `uuid` nativo), datetimes **UTC aware**. Al guardar se serializa
con `model_dump(mode="json")`; al leer se reconstruye con `Model.model_validate(...)`.
**Alembic** gestiona el esquema desde el día 1.

## 8. Capa de autenticación (`auth/`)

- **Primitivas** (`auth/security.py`): hash y verificación de contraseña con
  **argon2**; codificación/decodificación de JWT con **pyjwt**.
- **Servicio** (`auth/service.py`): `register` / `authenticate` y **rotación** de
  refresh tokens.
- **Modelo de tokens**: **access token** corto (vida `access_token_expire_minutes`,
  guardado solo en memoria del cliente, se manda por `Authorization: Bearer`) +
  **refresh token ROTATIVO persistido en DB** (tabla `RefreshToken`, solo su hash). El
  refresh **ya no viaja en el body**: vive y viaja en una **cookie httpOnly** (`Path=/auth`,
  `Max-Age` alineado con `refresh_token_expire_days`; `Secure`/`SameSite`/`Domain` por env),
  fuera del alcance de JS. La rotación/revocación en DB es **agnóstica al transporte** y no
  cambia: habilita **logout real** y "cerrar sesión en todos los dispositivos" desde Fase 1.
  Ver ADR-007 (modelo de tokens) y **ADR-011** (transporte del refresh en cookie httpOnly).
- **Recuperación de sesión (cold-start)**: al arrancar el frontend sin access en memoria,
  `POST /auth/refresh` (lee la cookie httpOnly) → access nuevo → `GET /auth/me` → user.
  `GET /auth/me` (Bearer → `{id, email, has_profile}`) es la **fuente de hidratación** de
  la sesión. Ver ADR-011.
- **`get_current_user`** (en `api/deps.py`): valida el access token, carga el `User` y
  lo inyecta en el handler.
- **`password_hash` es NULLABLE**, preparado para login OAuth futuro (ADR-009, Fase 4)
  sin migración disruptiva.
- **Aislamiento por usuario (bloqueante)**: toda query autenticada filtra por
  `current_user.id`. El acceso a un recurso ajeno devuelve **404, no 403** (no se
  revela la existencia del recurso). `user_id` se **denormaliza** en `Plan` y
  `ActivityProgress` para que el filtro de propiedad sea directo.

## 9. Capa API / routers (`api/`)

`main.py` queda fino: solo `include_router(...)` y el `lifespan` que compila el grafo
una vez y lo deja en `app.state.graph` (igual que hoy). Los routers viven en `api/`:

| Router               | Responsabilidad                                  |
| -------------------- | ------------------------------------------------ |
| `auth_router.py`     | register / login / refresh / logout / me         |
| `profile_router.py`  | onboarding y lectura/edición del perfil          |
| `plans_router.py`    | `POST /plans` (sustituye a `/coach`), historial  |
| `progress_router.py` | marcar actividad PENDING/DONE/SKIPPED            |

**Contrato de auth** (ver ADR-011): `TokenResponse` es **access-only**
(`{access_token, token_type}`); el refresh sale/entra por **cookie httpOnly**, no por el
body. `POST /auth/refresh` y `POST /auth/logout` van **sin body** (leen la cookie): el
primero rota la cookie y devuelve un access nuevo, el segundo la borra. `GET /auth/me`
(Bearer) es la fuente de **hidratación** de la sesión.

**Handlers finos**: validan el body (schemas de `api/schemas.py`), resuelven
dependencias y delegan. **Dónde se inyecta la sesión**: `get_db` (en `api/deps.py`,
reexportando `db.session.get_db`) entra **por request** como dependencia de FastAPI; el
**grafo compilado** vive en `app.state.graph` (no es per-request, se comparte). Esta
convivencia mantiene la frontera: el router pide la sesión a `db/`, invoca el grafo de
`graph/` y traduce con los mappers; el grafo nunca ve la sesión.

CORS se amplía respecto al MVP: se habilitan métodos **PUT/PATCH/DELETE**, el header
**Authorization** y **`allow_credentials=True`** con **origen explícito** desde config
(necesario para que el navegador envíe/reciba la cookie httpOnly del refresh en el
transporte directo cross-origin; incompatible con origen comodín). Ver ADR-011.

## 10. Modelo de datos

Mini-ER (1-1 y 1-N; todas las hijas cuelgan de `User` con **ON DELETE CASCADE**, ver
ADR-008):

```
            ┌───────────────┐
            │     User      │  id, email(uniq,lower), password_hash?, is_active, ts
            └───┬───┬───┬───┘
       1-1 ┌────┘   │   └────┐ 1-N
           ▼      1-N▼        ▼
     ┌──────────┐ ┌──────────┐ ┌──────────────┐
     │ Profile  │ │   Plan   │ │ RefreshToken │
     └──────────┘ └────┬─────┘ └──────────────┘
                       │ 1-N
                       ▼
                 ┌──────────────────┐
                 │ ActivityProgress │  (user_id denormalizado)
                 └──────────────────┘
```

Decisión **JSON-snapshot vs. normalización** (ADR-008): la salida del coach es un
**artefacto inmutable**. `Plan` guarda como **snapshot JSON** lo que no debe cambiar ni
re-derivarse —`input_profile_snapshot`, `input_usage_snapshot`, `plan` (WeeklyPlan),
`activities` (lista de CuratedActivity) y `derivation`—. Solo se **normaliza lo mutable
y consultable**: `ActivityProgress`. La **identidad de una actividad** es su
`activity_index` (posición en el array snapshotado de `activities`); **no** se añade
`id` a `CuratedActivity`. Así, marcar progreso referencia `(plan_id, activity_index)`
sin desnormalizar el contenido de la actividad.

Campos clave por entidad:

| Entidad            | Campos relevantes                                                                                                   |
| ------------------ | ------------------------------------------------------------------------------------------------------------------- |
| `User`             | id (UUID/str), email (único, lower), password_hash (nullable), is_active, timestamps                                |
| `Profile`          | user_id (FK único, 1-1), goals/interests/constraints (JSON), lang, **schema_version** (int), timestamps             |
| `Plan`             | user_id (FK idx), created_at, **status** GENERATED\|DERIVED, input_profile_snapshot, input_usage_snapshot, plan (JSON?), activities (JSON list), derivation (JSON?), errors (JSON list), auditoría: langfuse_trace_id / llm_provider / llm_model (nullable) |
| `ActivityProgress` | plan_id (FK idx), user_id (denormalizado), **activity_index** (int), status PENDING\|DONE\|SKIPPED, updated_at, **único (plan_id, activity_index)** |
| `RefreshToken`     | user_id (FK), token (hash), expires_at, revoked, soporte de rotación                                                |

## 11. Configuración

Variables nuevas en `Settings` (nada hardcodeado, CLAUDE.md §2):

| Variable                      | Defecto                  | Notas                                         |
| ----------------------------- | ------------------------ | --------------------------------------------- |
| `database_url`                | `sqlite:///./offbloom.db`| Migrable a Postgres sin reescritura (§7)      |
| `jwt_secret_key`              | **sin defecto**          | Obligatorio en producción                     |
| `jwt_algorithm`               | `HS256`                  |                                               |
| `access_token_expire_minutes` | `30`                     | Access token corto (en memoria en cliente)    |
| `refresh_token_expire_days`   | `14`                     | Refresh rotativo persistido en DB             |

## 12. Secuencia de `POST /plans`

`POST /plans` **sustituye** al antiguo `/coach`. El grafo **no cambia ni una línea**;
el endpoint solo orquesta persistencia alrededor de la invocación:

```
Cliente ──POST /plans {usage: UsageData} (Bearer access)──► plans_router
  1. validar body (schema) + get_current_user
  2. ProfileRepo.get(user_id) ── si no hay perfil ─► 404 (sin onboarding)
  3. mappers: Profile(ORM) ─► UserProfile(dominio)
  4. construir CoachState{ profile, usage }
  5. app.state.graph.invoke(state, callbacks=[langfuse_handler])
  6. mappers: result ─► Plan(row)
        ├─ result.derivation presente ─► status=DERIVED (guarda SOLO el
        │   DerivationMessage; sin teléfonos, sin diagnóstico, sin RiskSignal interno)
        └─ plan normal              ─► status=GENERATED (plan + activities snapshot)
     + auditoría: langfuse_trace_id / llm_provider / llm_model
  7. PlanRepo.create(...) (persistir)
  8. responder el Plan (200/201)
```

Notas:
- La **derivación se persiste** como un `Plan` con `status=DERIVED`; **nunca** se
  almacenan internos de riesgo (el `RiskSignal` del Analista no sale del grafo). Ver
  ADR-008 y `08-seguridad-y-limites.md`.
- La sesión de DB entra por dependency (`get_db`, §9); el grafo compilado se reutiliza
  desde `app.state` (no se recompila por request).
