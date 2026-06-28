"""Ejecuta el coach hasta el plan, de forma aislada, para evaluar groundedness.

A diferencia del gate (que solo corre el Analista), aquí necesitamos el plan
fundamentado, así que ejecutamos:

    analyst(state) -> {analysis, risk}
    route_after_analyst(...) -> "derivation" | "continue"
    planner(merged)          -> {plan, retrieved}   (si "continue")

Aplica el MISMO router del grafo en producción. Los casos del banco son del
listón alto (no deberían derivar), pero el Analista usa el LLM (8B, no
determinista): si en una corrida marca riesgo, lo registramos como `derived` y
ese run se EXCLUYE del scoring en vez de inventar una salida. Lo mismo si el
Planificador degrada sin emitir plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from coach.graph.graph import route_after_analyst
from coach.graph.nodes.analyst import analyst
from coach.graph.nodes.planner import planner
from coach.graph.state import CoachState, RetrievedChunk, WeeklyPlan


@dataclass(frozen=True)
class PlanRun:
    """Resultado de una ejecución del coach hasta el plan.

    - `plan`: el `WeeklyPlan` emitido, o None si no hubo plan (derivado o degradado).
    - `retrieved`: fragmentos recuperados por el RAG (el retrieval_context a contrastar).
    - `derived`: True si el gate derivó (el Analista marcó riesgo); ese run no puntúa.
    """

    plan: WeeklyPlan | None
    retrieved: list[RetrievedChunk] = field(default_factory=list)
    derived: bool = False


def run_plan(state: CoachState) -> PlanRun:
    """Corre Analista + router + Planificador sobre `state` y devuelve el plan.

    Si el gate deriva, devuelve un `PlanRun` sin plan marcado como `derived`. Si
    el Planificador degrada (devuelve `errors` sin `plan`), devuelve un `PlanRun`
    sin plan y `derived=False` (no se derivó, pero no hay plan que puntuar).
    """
    output = analyst(state)
    merged: CoachState = {**state, **output}

    if route_after_analyst(merged) == "derivation":
        return PlanRun(plan=None, retrieved=[], derived=True)

    result = planner(merged)
    plan = result.get("plan")
    if not isinstance(plan, WeeklyPlan):
        # El Planificador degradó (p. ej. salida del LLM con formato inesperado).
        return PlanRun(plan=None, retrieved=[], derived=False)

    retrieved = result.get("retrieved") or []
    return PlanRun(plan=plan, retrieved=list(retrieved), derived=False)


def serialize_plan(plan: WeeklyPlan) -> str:
    """Aplana el plan a texto legible para usarlo como `actual_output`.

    Incluye el foco semanal, las intenciones y las sustituciones (habit ->
    alternative). NO incluye las citas: no son afirmaciones a contrastar contra el
    contexto, sino metadatos de procedencia.
    """
    parts: list[str] = [f"Foco semanal: {plan.weekly_focus}"]
    if plan.intentions:
        parts.append("Intenciones:")
        parts.extend(f"- {intention}" for intention in plan.intentions)
    if plan.swaps:
        parts.append("Sustituciones:")
        parts.extend(f"- {swap.habit} -> {swap.alternative}" for swap in plan.swaps)
    return "\n".join(parts)


def retrieval_context(retrieved: list[RetrievedChunk]) -> list[str]:
    """Devuelve el texto de cada fragmento recuperado como `retrieval_context`."""
    return [chunk.text for chunk in retrieved]
