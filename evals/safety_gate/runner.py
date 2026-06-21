"""Ejecuta el gate de seguridad de forma aislada (solo hasta la decisión).

La decisión del gate está totalmente capturada por el Analista + la arista
condicional, sin necesidad del Planificador, el Curador ni el RAG:

    analyst(state) -> {analysis, risk}  ->  route_after_analyst(...) -> "derivation" | "continue"

Por eso `run_gate` corre SOLO el Analista (una llamada al LLM) y aplica el mismo
router que usa el grafo en producción. Esto hace la eval mucho más rápida y la
desacopla del índice de Chroma y de los embeddings.
"""

from __future__ import annotations

from dataclasses import dataclass

from coach.graph.graph import route_after_analyst
from coach.graph.nodes.analyst import analyst
from coach.graph.state import CoachState, Severity


@dataclass(frozen=True)
class GateDecision:
    """Resultado de una ejecución del gate sobre un estado de entrada.

    - `derive`: True si el gate toma la rama de derivación (la decisión que mide
      la eval).
    - `flag` / `severity` / `reason`: detalle de la `RiskSignal` del Analista.
    - `degraded`: True si el Analista degradó sin emitir `risk` (entrada
      inválida); en ese caso `derive=False`, por el contrato del router.
    """

    derive: bool
    flag: bool
    severity: Severity
    reason: str
    degraded: bool


def run_gate(state: CoachState) -> GateDecision:
    """Corre el Analista sobre `state` y devuelve la decisión del gate.

    Fusiona la salida del Analista en una copia del estado y aplica
    `route_after_analyst` —el mismo router del grafo— para decidir la rama.
    """
    output = analyst(state)
    merged: CoachState = {**state, **output}

    risk = merged.get("risk")
    branch = route_after_analyst(merged)
    derive = branch == "derivation"

    if risk is None:
        return GateDecision(
            derive=derive,
            flag=False,
            severity=Severity.NONE,
            reason="",
            degraded=True,
        )

    return GateDecision(
        derive=derive,
        flag=risk.flag,
        severity=risk.severity,
        reason=risk.reason,
        degraded=False,
    )
