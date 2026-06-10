"""Nodo Planificador: segundo nodo de la rama continue (risk=False).

Es el primer nodo que usa RAG (#1): recupera conocimiento del corpus con
`coach.rag` y produce un plan semanal fundamentado y citado. Filosofía
"sustituir, no prohibir": no bloquea apps, propone sustituciones y un foco
semanal anclados en los fragmentos recuperados.

Lee `analysis` (obligatorio) y `profile` (opcional, solo contexto) del estado y
emite `plan` (WeeklyPlan con citations) + `retrieved` (los fragmentos usados).
No diagnostica ni da consejo clínico.

Contrato: docs/02-architecture.md §2-§3.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from coach.graph.state import Analysis, CoachState, WeeklyPlan
from coach.llm import get_chat_model
from coach.rag.store import search_knowledge

PLANNER_SYSTEM_PROMPT = """\
Eres el Planificador de un coach de bienestar digital cuya filosofía es
"sustituir, no prohibir". A partir del análisis de la persona y de los
fragmentos de conocimiento recuperados, diseñas un plan semanal accionable:
un foco para la semana (weekly_focus), intenciones concretas (intentions) y
sustituciones de hábitos por alternativas mejores (swaps con habit/alternative).
No bloqueas ni prohíbes apps: propones sustituir el uso por algo que cubra la
misma necesidad.

Fundamentación (RAG). Fundamenta el plan ÚNICAMENTE en los fragmentos de
conocimiento que recibes. No uses conocimiento general ni inventes información
que no esté en esos fragmentos.

Citas. Rellena `citations` con las fuentes de los fragmentos que de verdad
usaste para fundamentar el plan: cada cita lleva `source` y, cuando lo conozcas,
`chunk_id` (el id del fragmento). ESTÁ PROHIBIDO inventar fuentes o ids: cita
solo fuentes presentes en los fragmentos recuperados. Si no se recuperó ningún
fragmento, deja `citations` vacío en lugar de inventar.

Seguridad (dominio sensible). No diagnosticas, no das consejo clínico, ni
nombres de fármacos o tratamientos. Te limitas al plan de bienestar digital.
"""


def _build_query(analysis: Analysis) -> str:
    """Construye la consulta en español para el retriever a partir del análisis.

    Combina patrones, disparadores y el mapeo uso→necesidad para que la búsqueda
    semántica recupere conocimiento relevante para fundamentar el plan.
    """
    parts: list[str] = ["Plan semanal de bienestar digital para sustituir el uso de pantalla."]
    if analysis.patterns:
        parts.append("Patrones: " + "; ".join(analysis.patterns) + ".")
    if analysis.triggers:
        parts.append("Disparadores: " + "; ".join(analysis.triggers) + ".")
    if analysis.needs_covered:
        needs = "; ".join(f"{m.use} cubre {m.need}" for m in analysis.needs_covered)
        parts.append("Necesidades cubiertas: " + needs + ".")
    return " ".join(parts)


def planner(state: CoachState) -> CoachState:
    """Recupera conocimiento y emite un `plan` semanal fundamentado + `retrieved`.

    Guardia de entrada: si falta `analysis`, no llama al retriever ni al LLM y
    degrada de forma controlada escribiendo en el canal `errors`. El `profile`
    es opcional: solo añade contexto si está presente.
    """
    analysis = state.get("analysis")
    if analysis is None:
        return {"errors": ["planner: falta analysis en el estado"]}
    profile = state.get("profile")

    query = _build_query(analysis)
    retrieved = search_knowledge(query, k=4)

    fragments = "\n\n".join(
        f"[{i}] id={chunk.id} | fuente={chunk.source}\n{chunk.text}"
        for i, chunk in enumerate(retrieved, start=1)
    )
    user_parts = [
        "Diseña el plan semanal a partir de estos datos.",
        f"ANÁLISIS (Analysis):\n{analysis.model_dump_json()}",
    ]
    if profile is not None:
        user_parts.append(f"PERFIL (UserProfile, solo contexto):\n{profile.model_dump_json()}")
    user_parts.append(
        "FRAGMENTOS DE CONOCIMIENTO RECUPERADOS (cita solo estas fuentes):\n"
        + (fragments if fragments else "(no se recuperó ningún fragmento)")
    )
    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content="\n\n".join(user_parts)),
    ]

    model = get_chat_model(temperature=0.3).with_structured_output(WeeklyPlan)
    plan = model.invoke(messages)
    if not isinstance(plan, WeeklyPlan):
        return {"errors": ["planner: salida del LLM con formato inesperado"]}

    return {"plan": plan, "retrieved": retrieved}
