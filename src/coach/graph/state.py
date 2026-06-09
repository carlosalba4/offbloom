"""Estado compartido del grafo del coach.

Define los canales del `CoachState` y los modelos Pydantic que viajan por ellos:
el perfil del usuario, los datos de uso, el análisis del Analista, la señal de
riesgo, los fragmentos recuperados por RAG, el plan semanal del Planificador y
las actividades offline del Curador.

Contrato: docs/02-architecture.md §2 y ADR-003.
"""
from __future__ import annotations

import enum
from typing import Annotated, TypedDict

from pydantic import BaseModel, ConfigDict, Field


def _accumulate(left: list[str] | None, right: list[str] | None) -> list[str]:
    """Reducer acumulador defensivo para el canal `errors`.

    Concatena los errores emitidos por varios nodos sin perder ninguno, aunque
    alguno de los lados sea `None`.
    """
    return [*(left or []), *(right or [])]


class Lang(enum.StrEnum):
    """Idioma de interacción con el usuario."""

    ES = "ES"
    EN = "EN"


class EnergyLevel(enum.StrEnum):
    """Nivel de energía disponible para una actividad."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Place(enum.StrEnum):
    """Lugar donde se puede realizar una actividad."""

    HOME = "HOME"
    OUTDOORS = "OUTDOORS"
    ANYWHERE = "ANYWHERE"


class SocialPreference(enum.StrEnum):
    """Preferencia social para una actividad."""

    SOLO = "SOLO"
    WITH_OTHERS = "WITH_OTHERS"
    ANY = "ANY"


class TimeOfDay(enum.StrEnum):
    """Momento del día."""

    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"
    EVENING = "EVENING"
    NIGHT = "NIGHT"


class Severity(enum.StrEnum):
    """Severidad de una señal de riesgo."""

    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ResourceType(enum.StrEnum):
    """Tipo de recurso de ayuda al que derivar."""

    MENTAL_HEALTH = "MENTAL_HEALTH"
    MEDICAL = "MEDICAL"
    CRISIS_SUPPORT = "CRISIS_SUPPORT"
    GENERAL = "GENERAL"


class Constraints(BaseModel):
    """Restricciones del usuario que condicionan las propuestas."""

    model_config = ConfigDict(extra="forbid")

    available_minutes: int = Field(description="Minutos disponibles para actividades.")
    energy: EnergyLevel = Field(description="Nivel de energía disponible.")
    place: Place = Field(description="Lugar donde puede realizar actividades.")
    social: SocialPreference = Field(description="Preferencia social del usuario.")


class UserProfile(BaseModel):
    """Perfil del usuario: objetivos, intereses y restricciones."""

    model_config = ConfigDict(extra="forbid")

    goals: list[str] = Field(default_factory=list, description="Objetivos del usuario.")
    interests: list[str] = Field(default_factory=list, description="Intereses del usuario.")
    constraints: Constraints = Field(
        description="Restricciones de tiempo, energía, lugar y social."
    )
    lang: Lang = Field(default=Lang.ES, description="Idioma de interacción.")


class CategoryUsage(BaseModel):
    """Uso diario de una categoría de aplicaciones."""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(description="Categoría de uso (p. ej. redes sociales).")
    minutes_per_day: int = Field(description="Minutos de uso al día en esta categoría.")


class UsageData(BaseModel):
    """Datos de uso (simulados o auto-reportados) del usuario."""

    model_config = ConfigDict(extra="forbid")

    categories: list[CategoryUsage] = Field(
        default_factory=list, description="Uso por categoría."
    )
    peak_windows: list[TimeOfDay] = Field(
        default_factory=list, description="Franjas horarias de mayor uso."
    )
    self_reported_triggers: list[str] = Field(
        default_factory=list, description="Disparadores reportados por el usuario."
    )


class NeedMapping(BaseModel):
    """Mapeo entre un uso y la necesidad que cubría."""

    model_config = ConfigDict(extra="forbid")

    use: str = Field(description="Uso concreto observado.")
    need: str = Field(description="Necesidad que cubría ese uso.")


class Analysis(BaseModel):
    """Hallazgos del Analista: patrones, disparadores y necesidades cubiertas."""

    model_config = ConfigDict(extra="forbid")

    patterns: list[str] = Field(default_factory=list, description="Patrones de uso detectados.")
    triggers: list[str] = Field(default_factory=list, description="Disparadores identificados.")
    needs_covered: list[NeedMapping] = Field(
        default_factory=list, description="Necesidades que cubría cada uso."
    )


class RiskSignal(BaseModel):
    """Señal de riesgo detectada en el dominio sensible de bienestar."""

    model_config = ConfigDict(extra="forbid")

    flag: bool = Field(description="Indica si se ha detectado una señal de riesgo.")
    reason: str = Field(default="", description="Motivo de la señal de riesgo.")
    severity: Severity = Field(
        default=Severity.NONE, description="Severidad de la señal de riesgo."
    )


class RetrievedChunk(BaseModel):
    """Fragmento de conocimiento recuperado por el RAG."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Identificador del fragmento.")
    text: str = Field(description="Texto del fragmento.")
    category: str = Field(description="Categoría temática del fragmento.")
    source: str = Field(description="Fuente del fragmento.")


class Swap(BaseModel):
    """Sustitución de un hábito por una alternativa."""

    model_config = ConfigDict(extra="forbid")

    habit: str = Field(description="Hábito a sustituir.")
    alternative: str = Field(description="Alternativa propuesta.")


class Citation(BaseModel):
    """Cita que respalda una propuesta del plan."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(description="Fuente citada.")
    chunk_id: str | None = Field(default=None, description="Identificador del fragmento citado.")


class WeeklyPlan(BaseModel):
    """Plan semanal del Planificador, fundamentado en conocimiento recuperado."""

    model_config = ConfigDict(extra="forbid")

    weekly_focus: str = Field(description="Foco de la semana.")
    intentions: list[str] = Field(default_factory=list, description="Intenciones de la semana.")
    swaps: list[Swap] = Field(default_factory=list, description="Sustituciones propuestas.")
    citations: list[Citation] = Field(
        default_factory=list, description="Citas que respaldan el plan."
    )


class CuratedActivity(BaseModel):
    """Actividad offline propuesta por el Curador, sensible al contexto."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="Título de la actividad.")
    reason: str = Field(description="Razón por la que se propone.")
    why_it_fits: str = Field(description="Por qué encaja con el usuario y su contexto.")
    replaces: str | None = Field(default=None, description="Hábito que sustituye.")
    source: str | None = Field(default=None, description="Fuente de la actividad.")
    duration_min: int | None = Field(default=None, description="Duración estimada en minutos.")
    energy: EnergyLevel | None = Field(default=None, description="Nivel de energía requerido.")
    place: Place | None = Field(default=None, description="Lugar de realización.")
    social: SocialPreference | None = Field(default=None, description="Preferencia social.")
    moment: TimeOfDay | None = Field(default=None, description="Momento del día sugerido.")


class DerivationMessage(BaseModel):
    """Mensaje de derivación a ayuda profesional.

    Por diseño de seguridad no incluye números de teléfono: la derivación apunta
    a un tipo de recurso, no a un contacto concreto.
    """

    model_config = ConfigDict(extra="forbid")

    message: str = Field(description="Mensaje de derivación al usuario.")
    resource_type: ResourceType = Field(description="Tipo de recurso de ayuda al que derivar.")


class CoachState(TypedDict, total=False):
    """Estado compartido entre los nodos del grafo del coach."""

    profile: UserProfile
    usage: UsageData
    analysis: Analysis
    risk: RiskSignal
    retrieved: list[RetrievedChunk]
    plan: WeeklyPlan
    activities: list[CuratedActivity]
    derivation: DerivationMessage | None
    errors: Annotated[list[str], _accumulate]
