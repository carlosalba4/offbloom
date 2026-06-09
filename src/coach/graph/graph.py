"""Ensambla el coach como un `StateGraph` de LangGraph.

Hoy cablea el gate de seguridad: Analyst -> (Derivation | continuar). Cuando una
señal de riesgo está activa, el grafo deriva a una respuesta de seguridad
curada; en caso contrario sigue su curso. El Planner y el Curador se añadirán en
la rama "continue" (ver PUNTO DE EXTENSIÓN), fundamentados vía coach.rag y
usando coach.llm.get_chat_model() para mantener el modelo agnóstico.

Contrato: docs/02-architecture.md §2-§3.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from coach.graph.nodes.analyst import analyst
from coach.graph.nodes.derivation import derivation
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

    builder.add_edge(START, "analyst")

    # PUNTO DE EXTENSIÓN: la rama "continue" apuntará al nodo `planner` cuando
    # exista. Hoy, sin Planner, termina el grafo en END.
    builder.add_conditional_edges(
        "analyst",
        route_after_analyst,
        {"derivation": "derivation", "continue": END},
    )
    builder.add_edge("derivation", END)

    return builder.compile()
