# ADR-002: Chroma embebido vs. servidor

- **Estado**: aceptado
- **Fecha**: 2026-06-08

## Contexto
El coach necesita un almacén vectorial para el RAG (dos colecciones: `knowledge` y
`activities`). El corpus es **pequeño y casi estático**. Prioridades del producto:
privacy-first/local, despliegue simple (un contenedor) y poca fricción operativa.

## Decisión
Usar **Chroma embebido** (`PersistentClient` con directorio persistente,
`CHROMA_DIR`) dentro del propio proceso de la app, para el MVP. Nada de un servicio
de base de datos vectorial separado. La construcción del store y un retriever limpio
se encapsulan en `src/coach/rag/` para que el resto del grafo no conozca el detalle.

## Consecuencias
- **Positivas**: cero infraestructura adicional; encaja con el modo 100% local
  (self-host con Ollama); despliegue como un solo contenedor; arranque simple en
  CI y en la demo.
- **Negativas**: sin escalado horizontal ni alta concurrencia (aceptable para el
  MVP/demo); la persistencia vive con el contenedor.
- **Ruta de migración**: si hiciera falta escalar, basta cambiar la construcción del
  cliente en `rag/store.py` (a Chroma en modo servidor u otro backend) sin tocar los
  nodos del grafo.
- **Liga con ADR-001**: en el perfil `api` la *query* aún necesita un embedder en
  runtime; precomputar/empaquetar el store en build es una de las vías para el demo
  alojado (ver `docs/02-architecture.md` §5).

## Alternativas descartadas
- **Chroma en modo servidor (cliente/servidor)** — más infraestructura y operación
  sin beneficio para el tamaño actual del corpus.
- **Qdrant / pgvector / otro servicio gestionado** — sobredimensionado para el MVP y
  rompería el modo self-host simple.
