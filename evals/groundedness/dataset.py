"""Banco de casos para evaluar la groundedness del plan del coach.

No duplica perfiles: reutiliza el banco del gate (`evals.safety_gate.dataset`) y
selecciona los casos del listón ALTO que SÍ deberían continuar hasta el plan (no
derivar). Sobre esos casos se mide si el `WeeklyPlan` resultante está
fundamentado en los fragmentos recuperados por el RAG.

Los casos de riesgo (red sensible) se excluyen a propósito: ahí el grafo deriva y
no hay plan que contrastar; esa decisión la cubre la suite del gate.
"""

from __future__ import annotations

from dataclasses import dataclass

from coach.graph.state import CoachState
from evals.safety_gate.dataset import GateCase, build_gate_cases

# Etiquetas del banco del gate que SÍ generan plan (listón alto / no deriva).
# Se eligen casos representativos del caso de uso del coach.
GROUNDEDNESS_LABELS: tuple[str, ...] = (
    "scroll-nocturno-fomo",
    "procrastinacion-aburrimiento",
    "deseo-reducir-pantalla",
    "moderado-sano",
)


@dataclass(frozen=True)
class GroundednessCase:
    """Un caso para evaluar la groundedness del plan.

    - `label`: nombre corto del escenario (reaprovechado del banco del gate).
    - `state`: el `CoachState` de entrada que se pasa al grafo (perfil + uso).
    """

    label: str
    state: CoachState


def build_groundedness_cases() -> list[GroundednessCase]:
    """Construye el banco de casos de groundedness a partir del banco del gate.

    Toma los `GateCase` cuyas etiquetas están en `GROUNDEDNESS_LABELS` y reaprovecha
    su `.label` y `.state`, preservando el orden de `GROUNDEDNESS_LABELS`.
    """
    by_label: dict[str, GateCase] = {case.label: case for case in build_gate_cases()}

    cases: list[GroundednessCase] = []
    for label in GROUNDEDNESS_LABELS:
        gate_case = by_label.get(label)
        if gate_case is None:
            raise KeyError(
                f"El banco del gate no contiene el caso esperado {label!r}; "
                "revisa GROUNDEDNESS_LABELS frente a evals.safety_gate.dataset."
            )
        cases.append(GroundednessCase(label=gate_case.label, state=gate_case.state))
    return cases
