# ADR-003: Contrato de estado del grafo (`CoachState`) y gate de seguridad

- **Estado**: aceptado
- **Fecha**: 2026-06-08

## Contexto
El coach es un grafo LangGraph con varios nodos (Analista, Planificador, Curador y
Derivación) que se comunican por un **estado compartido**. Necesitamos un contrato
explícito de qué lleva ese estado —para desacoplar los nodos y permitir que
`agent-engineer` implemente sin ambigüedad— con tipado estricto (CLAUDE.md prohíbe
`Any` evitables) y un punto claro donde se decide la **seguridad** (requisito
bloqueante).

## Decisión
`CoachState` es un `TypedDict(total=False)` (semántica de canales de LangGraph)
cuyos campos son **modelos Pydantic v2**: `profile`, `usage`, `analysis`, `risk`,
`retrieved`, `plan`, `activities`, `derivation`, `errors` (contrato detallado en
`docs/02-architecture.md` §2). Cada nodo valida en su frontera y produce salida con
`with_structured_output(<Modelo>)`.

El **gate de seguridad** se modela dentro de este contrato: el Analista emite un
`RiskSignal` (`flag/reason/severity`) y una **arista condicional** sobre `risk.flag`
desvía al nodo **Derivación** (que se salta Planificador y Curador) o continúa el
flujo normal.

## Consecuencias
- **Positivas**: contrato único y tipado para todos los nodos; nodos desacoplados
  (se comunican solo por el estado); validación en frontera; la seguridad es
  explícita, trazable y evaluable (no oculta en prompts).
- **Negativas**: combinar `TypedDict` (canales) con sub-modelos Pydantic exige
  disciplina al definir *reducers*/merges de estado; algo más de *boilerplate* de
  modelos.
- Si el gate de seguridad creciera en complejidad (varias políticas, severidades con
  rutas distintas), se extraería a un **ADR-004** dedicado.

## Alternativas descartadas
- **`dict` plano sin validar** — pierde el tipado estricto y la validación en
  frontera; frágil entre nodos.
- **Estado 100% Pydantic (`BaseModel` como state)** — viable, pero el `TypedDict`
  encaja mejor con los canales/reducers de LangGraph manteniendo Pydantic en los
  campos.
- **Un único *blob* de salida** — acopla los nodos y dificulta evaluar cada etapa
  por separado.
- **Seguridad solo en prompts/evals (sin nodo ni routing)** — el desvío a derivación
  queda implícito y es más difícil de garantizar para un requisito bloqueante.
