"""Nodo Curador: último nodo de la rama continue (risk=False).

Es el segundo nodo que usa RAG (#2): recupera del catálogo de actividades
offline con `coach.rag` y propone hasta 3 actividades sensibles al contexto.
Es el diferenciador del producto, filosofía "sustituir, no prohibir": no bloquea
apps, ofrece alternativas concretas que cubren la misma necesidad que el uso de
pantalla.

Lee `analysis` (obligatorio) y `profile` (opcional, solo contexto) del estado y
emite `activities` (lista de CuratedActivity). Reparto de responsabilidades: el
LLM SOLO selecciona entre los candidatos recuperados y explica su elección
(reason, why_it_fits, replaces, moment); los campos factuales de cada actividad
(title, duration_min, energy, place, social, source) se construyen de forma
determinista desde el `RetrievedActivity` elegido, sin que el LLM los invente.
No diagnostica ni da consejo clínico.

Contrato: docs/02-architecture.md §2-§3, ADR-003.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict

from coach.graph.state import (
    Analysis,
    CoachState,
    CuratedActivity,
    EnergyLevel,
    Lang,
    Place,
    SocialPreference,
    TimeOfDay,
    UserProfile,
)
from coach.llm import get_chat_model
from coach.rag.store import RetrievedActivity, search_activities

CURATOR_SYSTEM_PROMPT = """\
Eres el Curador de un coach de bienestar digital cuya filosofía es
"sustituir, no prohibir". Tu trabajo es proponer actividades offline concretas
que sustituyan el uso de pantalla cubriendo la misma necesidad de la persona.

Selección. Recibes una lista numerada de actividades candidatas recuperadas del
catálogo. Elige hasta 3 actividades ÚNICAMENTE entre esas candidatas y refiérete
a ellas usando exactamente su `activity_id`. ESTÁ PROHIBIDO inventar actividades
o identificadores que no estén en la lista de candidatas.

Fundamentación. Para cada elección rellena:
- reason: por qué propones esta actividad para esta persona.
- why_it_fits: por qué encaja con su contexto (restricciones de tiempo, energía,
  lugar y social; sus disparadores; las necesidades que cubría el uso).
- replaces: el hábito o disparador concreto que sustituye, si aplica (o nulo).
- moment: el momento del día más adecuado, si aplica (o nulo).
Apóyate solo en el análisis y el contexto que recibes; no inventes datos.

Seguridad (dominio sensible). No diagnosticas, no das consejo clínico, ni
nombres de fármacos o tratamientos. Te limitas a sugerir actividades de
bienestar digital.
"""

# ---------------------------------------------------------------------------
# Mapas inversos: string del corpus (español) → enum del dominio (state.py)
# ---------------------------------------------------------------------------

_ENERGY_INVERSE: dict[str, EnergyLevel] = {
    "baja": EnergyLevel.LOW,
    "media": EnergyLevel.MEDIUM,
    "alta": EnergyLevel.HIGH,
}

_PLACE_INVERSE: dict[str, Place] = {
    "casa": Place.HOME,
    "exterior": Place.OUTDOORS,
    "cualquiera": Place.ANYWHERE,
}

_SOCIAL_INVERSE: dict[str, SocialPreference] = {
    "solo": SocialPreference.SOLO,
    "social": SocialPreference.WITH_OTHERS,
    "either": SocialPreference.ANY,
    "cualquiera": SocialPreference.ANY,
}

# Tamaño del pool de candidatos recuperados y número objetivo de propuestas.
_CANDIDATE_POOL = 8
_TARGET = 3


# ---------------------------------------------------------------------------
# Modelos de salida estructurada interna (no forman parte del contrato compartido)
# ---------------------------------------------------------------------------


class _ActivityChoice(BaseModel):
    """Elección individual del LLM: referencia a un candidato + su justificación.

    El LLM solo selecciona y explica; los campos factuales de la actividad se
    construyen de forma determinista a partir del `RetrievedActivity` elegido.
    """

    model_config = ConfigDict(extra="forbid")

    activity_id: str
    reason: str
    why_it_fits: str
    replaces: str | None = None
    moment: TimeOfDay | None = None


class _CuratorOutput(BaseModel):
    """Salida estructurada interna del nodo Curador: las actividades elegidas."""

    model_config = ConfigDict(extra="forbid")

    activities: list[_ActivityChoice]


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------


def _build_query(analysis: Analysis, profile: UserProfile | None) -> str:
    """Construye la consulta en español para el retriever de actividades.

    Espejo de `planner._build_query`, orientada a actividades offline: combina
    patrones, disparadores y el mapeo uso→necesidad y, si hay perfil, añade
    intereses y objetivos para acercar la búsqueda semántica al contexto.
    """
    parts: list[str] = ["Actividades offline para sustituir el uso de pantalla."]
    if analysis.patterns:
        parts.append("Patrones: " + "; ".join(analysis.patterns) + ".")
    if analysis.triggers:
        parts.append("Disparadores: " + "; ".join(analysis.triggers) + ".")
    if analysis.needs_covered:
        needs = "; ".join(f"{m.use} cubre {m.need}" for m in analysis.needs_covered)
        parts.append("Necesidades cubiertas: " + needs + ".")
    if profile is not None:
        if profile.interests:
            parts.append("Intereses: " + "; ".join(profile.interests) + ".")
        if profile.goals:
            parts.append("Objetivos: " + "; ".join(profile.goals) + ".")
    return " ".join(parts)


def _retrieve_candidates(
    query: str,
    analysis: Analysis,
    *,
    max_duration_min: int | None,
    energy: EnergyLevel | None,
    place: Place | None,
    social: SocialPreference | None,
) -> list[RetrievedActivity]:
    """Recupera candidatos con una escalera de fallback de filtros decreciente.

    Aplica etapas de filtrado cada vez más laxas y se queda con la primera que
    alcanza al menos `_TARGET` resultados. Si ninguna lo alcanza, usa la primera
    etapa no vacía. Si todas quedan vacías, devuelve lista vacía. El `moment`
    nunca se usa como filtro (lo decide el LLM por cada actividad).
    """
    # Etapas de menor a mayor laxitud. Los triggers son texto libre y casan
    # exacto raramente: por eso `replaces` solo se intenta en la primera etapa.
    stages: list[dict[str, object]] = [
        {
            "max_duration_min": max_duration_min,
            "energy": energy,
            "place": place,
            "social": social,
            "replaces": analysis.triggers or None,
        },
        {
            "max_duration_min": max_duration_min,
            "energy": energy,
            "place": place,
            "social": social,
        },
        {
            "max_duration_min": max_duration_min,
            "energy": energy,
        },
        {},
    ]

    first_non_empty: list[RetrievedActivity] = []
    for stage in stages:
        candidates = search_activities(query, **stage, k=_CANDIDATE_POOL)  # type: ignore[arg-type]
        if len(candidates) >= _TARGET:
            return candidates
        if candidates and not first_non_empty:
            first_non_empty = candidates
    return first_non_empty


def _serialize_candidates(candidates: list[RetrievedActivity], lang: Lang) -> str:
    """Serializa los candidatos numerados para el prompt del LLM.

    Incluye solo lo que el LLM necesita para elegir y explicar; los campos
    factuales se reconstruyen luego de forma determinista desde el candidato.
    """
    lines: list[str] = []
    for i, c in enumerate(candidates, start=1):
        name = c.name_es if lang == Lang.ES else c.name_en
        lines.append(
            f"[{i}] activity_id={c.id} | nombre={name}\n"
            f"    descripcion: {c.text}\n"
            f"    duracion_min: {c.duration_min} | energia: {c.energy} | "
            f"lugar: {c.place} | social: {c.social}\n"
            f"    reemplaza: {', '.join(c.replaces) or '(ninguno)'} | "
            f"momento: {', '.join(c.moment) or '(cualquiera)'}\n"
            f"    materiales: {c.materials or '(ninguno)'}"
        )
    return "\n".join(lines)


def _to_curated(choice: _ActivityChoice, rid: RetrievedActivity, lang: Lang) -> CuratedActivity:
    """Construye una `CuratedActivity` combinando elección del LLM y candidato.

    Campos factuales (title, duration_min, energy, place, social, source) desde
    el `RetrievedActivity`; campos explicativos (reason, why_it_fits, replaces,
    moment) desde la elección del LLM.
    """
    return CuratedActivity(
        title=rid.name_es if lang == Lang.ES else rid.name_en,
        reason=choice.reason,
        why_it_fits=choice.why_it_fits,
        replaces=choice.replaces,
        source=f"catalogo:{rid.id}",
        duration_min=rid.duration_min,
        energy=_ENERGY_INVERSE.get(rid.energy),
        place=_PLACE_INVERSE.get(rid.place, Place.ANYWHERE),
        social=_SOCIAL_INVERSE.get(rid.social, SocialPreference.ANY),
        moment=choice.moment,
    )


# ---------------------------------------------------------------------------
# Nodo
# ---------------------------------------------------------------------------


def curator(state: CoachState) -> CoachState:
    """Recupera actividades offline y emite hasta 3 `activities` contextualizadas.

    Guardia de entrada: si falta `analysis`, no llama al retriever ni al LLM y
    degrada de forma controlada escribiendo en el canal `errors`. El `profile`
    es opcional: aporta contexto y mapea las restricciones a filtros del RAG.
    """
    analysis = state.get("analysis")
    if analysis is None:
        return {"errors": ["curator: falta analysis en el estado"]}
    profile = state.get("profile")

    # Contexto → filtros del retriever (los tipos del perfil ya son los enums).
    if profile is not None:
        constraints = profile.constraints
        max_duration_min: int | None = constraints.available_minutes
        energy: EnergyLevel | None = constraints.energy
        place: Place | None = constraints.place
        social: SocialPreference | None = constraints.social
        lang = profile.lang
    else:
        max_duration_min = None
        energy = None
        place = None
        social = None
        lang = Lang.ES

    query = _build_query(analysis, profile)
    candidates = _retrieve_candidates(
        query,
        analysis,
        max_duration_min=max_duration_min,
        energy=energy,
        place=place,
        social=social,
    )

    if not candidates:
        return {
            "activities": [],
            "errors": ["curator: no se recuperaron actividades para el contexto"],
        }

    pool: dict[str, RetrievedActivity] = {c.id: c for c in candidates}

    user_parts = [
        "Elige hasta 3 actividades SOLO entre estas candidatas y fundamenta tu elección.",
        f"ANÁLISIS (Analysis):\n{analysis.model_dump_json()}",
    ]
    if profile is not None:
        user_parts.append(f"PERFIL (UserProfile, solo contexto):\n{profile.model_dump_json()}")
    user_parts.append(
        "ACTIVIDADES CANDIDATAS (usa exactamente sus activity_id):\n"
        + _serialize_candidates(candidates, lang)
    )
    messages = [
        SystemMessage(content=CURATOR_SYSTEM_PROMPT),
        HumanMessage(content="\n\n".join(user_parts)),
    ]

    model = get_chat_model(temperature=0.3).with_structured_output(_CuratorOutput)
    result = model.invoke(messages)
    if not isinstance(result, _CuratorOutput):
        return {"errors": ["curator: salida del LLM con formato inesperado"]}

    # Construcción determinista: descarta ids alucinados y trunca a 3.
    activities: list[CuratedActivity] = []
    for choice in result.activities:
        rid = pool.get(choice.activity_id)
        if rid is None:
            continue
        activities.append(_to_curated(choice, rid, lang))
        if len(activities) >= _TARGET:
            break

    if not activities:
        return {"activities": [], "errors": ["curator: ninguna selección válida del LLM"]}

    return {"activities": activities}
