# ADR-001: Capa LLM agnóstica (factory por `LLM_PROVIDER`)

- **Estado**: aceptado
- **Fecha**: 2026-06-08

## Contexto
El producto debe demostrar **dos modos**: privacidad local (Ollama) y demo público
(API en la nube), seleccionables sin tocar el dominio. CLAUDE.md fija como regla de
oro que **ningún módulo importe un modelo concreto**. Necesitamos un único punto de
construcción del modelo de chat y de los embeddings.

## Decisión
Una capa `coach.llm` expone dos factories —`get_chat_model()` y
`get_embeddings()`— que eligen la implementación según `settings.llm_provider`
(env `LLM_PROVIDER`): `ollama` (local) u `openai`/`google`/`anthropic` (nube). Los
imports de cada SDK son **perezosos**, así solo se instala el paquete del proveedor
que se use. El resto del código (grafo, RAG, presentación) **solo** llama a estas
factories; nunca importa una clase de modelo concreta. Ya implementado en
`src/coach/llm/provider.py`.

## Consecuencias
- **Positivas**: cambiar local ↔ nube es una sola variable de entorno; se demuestra
  la privacidad como capacidad de arquitectura; los nodos del grafo quedan
  desacoplados del proveedor; dependencias mínimas por imports perezosos.
- **Negativas / pendiente**: hoy `get_embeddings()` está atada a Ollama. En el
  perfil `api` (demo alojado) el contenedor no alcanza Ollama, así que la capa debe
  **extender el ruteo a embeddings** (o precomputar el store en build). Queda como
  item de seguimiento; ver `docs/02-architecture.md` §5 y ADR-002.

## Alternativas descartadas
- **SDK directo en cada módulo** — viola la regla de oro y acopla el dominio al
  proveedor.
- **Proxy unificado (tipo LiteLLM/gateway)** — infraestructura extra innecesaria
  para el MVP; las factories perezosas bastan.
- **Modelo hardcodeado** — impide el modo dual local/nube, que es parte del valor.
