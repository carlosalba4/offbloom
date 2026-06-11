"""Ensambla el coach como un `StateGraph` de LangGraph.

Cablea el gate de seguridad: Analyst -> (Derivation | continuar). Cuando una
señal de riesgo está activa, el grafo deriva a una respuesta de seguridad
curada; en caso contrario la rama "continue" sigue su curso: Planner -> Curator
-> END. El Planner fundamenta el plan semanal vía coach.rag y el Curador propone
actividades offline; ambos usan coach.llm.get_chat_model() para mantener el
modelo agnóstico.

Contrato: docs/02-architecture.md §2-§3.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from coach.graph.nodes.analyst import analyst
from coach.graph.nodes.curator import curator
from coach.graph.nodes.derivation import derivation
from coach.graph.nodes.planner import planner
from coach.graph.state import CoachState


def route_after_analyst(state: CoachState) -> str:
    """Decide la rama tras el Analista.

    Devuelve "derivation" si hay una señal de riesgo activa (`risk.flag`); en
    cualquier otro caso (sin riesgo o estado degradado sin `risk`) devuelve
    "continue".
    """
    risk = state.get("risk")
    if risk is not None and risk.flag:
        return "derivation"
    return "continue"


def build_coach_graph() -> CompiledStateGraph:
    """Construye y compila el grafo del coach con el gate de seguridad."""
    builder: StateGraph = StateGraph(CoachState)

    builder.add_node("analyst", analyst)
    builder.add_node("derivation", derivation)
    builder.add_node("planner", planner)
    builder.add_node("curator", curator)

    builder.add_edge(START, "analyst")

    # Gate de seguridad: si hay riesgo se deriva; si no, la rama "continue"
    # recorre el flujo principal Planner -> Curator -> END.
    builder.add_conditional_edges(
        "analyst",
        route_after_analyst,
        {"derivation": "derivation", "continue": "planner"},
    )
    builder.add_edge("derivation", END)

    # Rama "continue": planificación fundamentada y curación de actividades.
    builder.add_edge("planner", "curator")
    builder.add_edge("curator", END)

    return builder.compile()
