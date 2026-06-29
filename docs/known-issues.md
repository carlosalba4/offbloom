# Limitaciones conocidas y deuda técnica

Este documento lista, con honestidad, las limitaciones conocidas y la deuda técnica
actual de OffBloom. El objetivo es que cualquiera que use o evalúe el proyecto sepa
qué esperar y qué está pendiente de pulir. Ninguna de estas limitaciones bloquea el
funcionamiento del coach; se indica en cada caso el impacto real.

## Datos

### Mapeo de `moment` en actividades
- **Qué es:** el momento del día de las actividades no se alinea con el contexto
  temporal del usuario (p. ej. el LLM traducía el token español "tarde" del corpus
  a `AFTERNOON` aunque la persona fuese nocturna).
- **Causa:** doble. (1) El corpus de actividades (`data/corpus/actividades.jsonl`)
  solo distingue `{manana, tarde, noche}`, sin separar *afternoon*/*evening*. (2) El
  contexto temporal del usuario (`peak_windows`, en `UsageData`) nunca llega al
  Curador, así que el LLM elegía el momento sin señal para desambiguar.
- **Impacto:** cosmético. La actividad sugerida sigue siendo apropiada; solo la
  etiqueta del momento podía sonar imprecisa.
- **Mitigación actual (parche):** el Curador (`src/coach/graph/nodes/curator.py`,
  `_to_curated`) emite siempre `moment = None` en lugar de un valor adivinado; así no
  se muestra un dato falso (el frontend omite el badge cuando es `None`).
- **Arreglo completo (diferido a la fase de expansión):** cablear `peak_windows`
  (de `UsageData`) al Curador para desambiguar tarde/atardecer/noche y, opcionalmente,
  pulir el etiquetado temporal del corpus.

## Frontend

### Duplicación manual de tipos frontend/backend
- **Qué es:** los tipos TypeScript del frontend (`frontend/src/lib/coach.ts`) son una
  copia manual de los modelos Pydantic del backend.
- **Causa:** se mantienen a mano; no hay generación automática desde el esquema de la API.
- **Impacto:** riesgo de desincronización si se cambia un lado sin el otro (un cambio
  en un modelo Pydantic no se refleja solo en el tipo TypeScript).
- **Mejora futura:** generar los tipos a partir del OpenAPI de la API.

### Favicon/logo SVG
- **Qué es:** `frontend/src/app/favicon.svg` es un PNG envuelto en SVG (generado por
  RealFaviconGenerator), no un vector puro.
- **Causa:** se generó a partir de un mapa de bits, no de un trazado vectorial.
- **Impacto:** ninguno funcional; el favicon se ve correctamente.
- **Mejora futura:** sustituirlo por un SVG vectorial real.

## CI

### Warnings de dependencias de terceros
- **Qué es:** avisos de deprecación que no provienen de código propio:
  - (a) deprecaciones de `httpx`/`starlette` al ejecutar `pytest`.
  - (b) deprecación de Node.js 20 en las acciones del workflow de CI
    (`checkout@v4`, `setup-uv@v5`).
- **Causa:** versiones actuales de dependencias y acciones de terceros.
- **Impacto:** cosmético; no afecta a los resultados de tests ni a la CI.
- **Plan:** se resolverán al actualizar dependencias y acciones cuando sus
  mantenedores publiquen nuevas versiones.

## Evals

### Juez local de groundedness no fiable
- **Qué es:** el juez LLM local (`qwen3:8b`) no discrimina bien la fundamentación de
  los planes.
- **Causa y detalle:** documentado en profundidad en
  [ADR-005](decisions/ADR-005-juez-local-groundedness.md).
- **Impacto:** las métricas de groundedness con juez local no son fiables.
- **Mitigación:** la suite de evals queda lista para conectar un juez de API.

### Juez de API pendiente para groundedness
- **Qué es:** las métricas de calidad del plan (fundamentación) no son fiables hasta
  usar un juez de API más capaz.
- **Causa:** ligada directamente al punto anterior (limitación del juez local 8B).
- **Impacto:** no se debe confiar en los scores de groundedness actuales para tomar
  decisiones de calidad.
- **Plan:** habilitar un juez de API y re-ejecutar la suite.

## Operación

### Dependencia del directorio de arranque (RAG)
- **Qué es:** la API debe lanzarse desde la raíz del proyecto para que el RAG localice
  el índice `.chroma`.
- **Causa:** la ruta del store es relativa (`settings.chroma_dir`, usada en
  `src/coach/rag/store.py`); se resuelve respecto al directorio de trabajo actual.
- **Impacto:** si se arranca desde otro directorio, el RAG no encuentra el índice y
  las búsquedas devuelven resultados vacíos.
- **Plan:** usar rutas configurables/absolutas en la fase de despliegue.
