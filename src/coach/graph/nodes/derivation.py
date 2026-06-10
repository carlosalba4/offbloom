"""Nodo Derivación: respuesta de seguridad ante una señal de riesgo.

Se activa cuando el Analista marca `risk.flag=True`. NO usa LLM: emite un
mensaje cuidado, determinista y predecible, anclado en
data/corpus/08-seguridad-y-limites.md. En un dominio sensible y bloqueante un
texto curado evita alucinaciones, teléfonos inventados o consejo clínico, y es
trivial de evaluar.

Comportamiento (08-seguridad-y-limites.md): empatía sin juzgar, reencuadre
(la recaída no es un fracaso), redirección con suavidad a un profesional de la
salud o a una persona de confianza. PROHIBIDO: números de teléfono o cualquier
dígito de contacto, consejo clínico, nombres de fármacos o "tratamientos".

Contrato: docs/02-architecture.md §3.
"""

from __future__ import annotations

from coach.graph.state import (
    CoachState,
    DerivationMessage,
    Lang,
    ResourceType,
    Severity,
)

# Mapeo determinista severidad -> tipo de recurso al que apuntar.
_RESOURCE_BY_SEVERITY: dict[Severity, ResourceType] = {
    Severity.HIGH: ResourceType.CRISIS_SUPPORT,
    Severity.MEDIUM: ResourceType.MENTAL_HEALTH,
}

# Plantillas curadas. {reflection} se rellena con un reflejo suave de
# risk.reason cuando está presente (o cadena vacía si no lo está).
_MESSAGE_ES = (
    "Gracias por compartir esto; hace falta valor para nombrar lo que sientes, "
    "y lo que sientes es válido.{reflection} Tener un día difícil o una recaída "
    "no es un fracaso: es parte del camino y no borra tu progreso. "
    "Aun así, esto que describes va más allá de un hábito y no es algo que tengas "
    "que sostener en soledad. Con suavidad te animo a apoyarte en un profesional "
    "de la salud o en una persona de confianza, y a buscar ayuda cuando lo "
    "necesites. Cuidarte de esa forma también es un acto de bienestar."
)

_MESSAGE_EN = (
    "Thank you for sharing this; it takes courage to name what you feel, and "
    "what you feel is valid.{reflection} Having a hard day or a relapse is not a "
    "failure: it is part of the journey and it does not erase your progress. "
    "Even so, what you describe goes beyond a habit and is not something you have "
    "to carry alone. Gently, I encourage you to lean on a health professional or "
    "on someone you trust, and to reach out for help when you need it. Caring for "
    "yourself that way is also an act of well-being."
)

_REFLECTION_ES = " Entiendo que esto tiene que ver con {reason}."
_REFLECTION_EN = " I understand this has to do with {reason}."


def _build_reflection(reason: str, lang: Lang) -> str:
    """Construye un reflejo suave del motivo de riesgo, o cadena vacía.

    Se omite cualquier dígito presente en el motivo para no filtrar números de
    contacto u otra información sensible en el mensaje curado.
    """
    clean = reason.strip()
    if not clean:
        return ""
    # Defensa: ningún dígito debe llegar al mensaje final.
    clean = "".join(ch for ch in clean if not ch.isdigit()).strip()
    if not clean:
        return ""
    template = _REFLECTION_EN if lang is Lang.EN else _REFLECTION_ES
    return template.format(reason=clean)


def derivation(state: CoachState) -> CoachState:
    """Emite un `DerivationMessage` curado a partir de `risk`.

    Guardia de entrada: si falta `risk` o `risk.flag` es False, este nodo no
    debería haberse alcanzado; degrada de forma controlada escribiendo en el
    canal `errors` y NO emite `derivation`.
    """
    risk = state.get("risk")
    if risk is None or not risk.flag:
        return {"errors": ["derivation: estado sin risk.flag activo"]}

    resource_type = _RESOURCE_BY_SEVERITY.get(risk.severity, ResourceType.GENERAL)

    profile = state.get("profile")
    lang = profile.lang if profile is not None else Lang.ES

    template = _MESSAGE_EN if lang is Lang.EN else _MESSAGE_ES
    reflection = _build_reflection(risk.reason, lang)
    message = template.format(reflection=reflection)

    return {"derivation": DerivationMessage(message=message, resource_type=resource_type)}
