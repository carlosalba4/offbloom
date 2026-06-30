# ADR-006: Capa de persistencia y ORM (SQLAlchemy 2.0 sync, frontera dominio/ORM)

- **Estado**: aceptado
- **Fecha**: 2026-06-30

## Contexto
OffBloom pasa de un coach sin estado a una app con cuentas, historial de planes y
progreso. Necesitamos persistencia sin romper la regla de oro de la arquitectura: el
dominio del coach (`graph/`, `rag/`) no debe conocer ni el framework web ni la base de
datos. El dominio ya tiene su fuente de verdad en los modelos Pydantic v2 de
`graph/state.py` (ADR-003); la persistencia no debe duplicar ni redefinir esas formas.
Además queremos desarrollar simple (SQLite) pero poder escalar a PostgreSQL sin
reescribir, y mantener coherencia con los handlers síncronos y `graph.invoke()`
bloqueante.

## Decisión
Añadir una capa `db/` con **SQLAlchemy 2.0 en modo SÍNCRONO**: `base.py`
(`DeclarativeBase`), `engine.py`, `session.py` (`get_db` como generador síncrono, una
sesión por request), `models/` (ORM), `repositories.py` (queries con filtro de
propiedad) y `mappers.py`.

- **`graph/` y `rag/` no importan `db/`** (ni `auth/` ni `api/`). El **único puente**
  ORM↔dominio son mappers explícitos en `db/mappers.py`: el dominio Pydantic manda; la
  persistencia guarda y reconstruye esas formas.
- **SQLite en desarrollo** (`database_url` por defecto `sqlite:///./offbloom.db`),
  **migrable a PostgreSQL sin reescritura**: columnas **JSON** (variante **JSONB** en
  Postgres), UUID como `String(36)`/GUID portable (no `uuid` nativo), datetimes **UTC
  aware**. Al guardar, `model_dump(mode="json")`; al leer, `Model.model_validate(...)`.
- **Alembic desde el día 1** para versionar el esquema.
- La salida del coach es un **artefacto inmutable**: `WeeklyPlan`, `activities` y
  `derivation` se guardan como **snapshot JSON**. Solo se **normaliza lo mutable y
  consultable** (el progreso); el detalle de la normalización vive en ADR-008.

## Consecuencias
- **Positivas**: frontera dominio/ORM nítida y verificable; cero reescritura para pasar
  a Postgres; modo sync coherente con FastAPI threadpool y `graph.invoke()`; el snapshot
  JSON conserva la trazabilidad histórica de cada plan tal y como se generó; Alembic
  evita drift de esquema.
- **Negativas**: los mappers son boilerplate que hay que mantener al evolucionar el
  dominio; el snapshot JSON no es consultable por campos internos (aceptable: el plan es
  inmutable, no se filtra por su contenido); SQLite tiene límites de concurrencia (solo
  desarrollo).

## Alternativas descartadas
- **SQLAlchemy async** — propaga `async`/`await` por toda la capa sin beneficio real
  con `graph.invoke()` bloqueante y handlers `def`.
- **ORM como fuente de verdad de las formas** — duplicaría y desincronizaría los modelos
  Pydantic del dominio; rompe ADR-003.
- **Persistir todo normalizado (sin snapshot)** — re-derivar un plan histórico es
  imposible/frágil y acopla el esquema a la forma interna del coach.
- **Empezar en Postgres** — más fricción operativa para el MVP; la portabilidad
  diseñada hace la migración trivial cuando haga falta.
- **Sin Alembic (create_all)** — inviable en cuanto el esquema evoluciona con datos
  reales.
