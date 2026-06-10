"""Nodo Analista: entrada del grafo del coach.

Lee `profile` + `usage` del estado y emite `analysis` (patrones, disparadores y
necesidades que cubría cada uso) y `risk` (señal de riesgo del dominio sensible).
No usa RAG ni diagnostica: se basa solo en los datos de la propia persona.

Contrato: docs/02-architecture.md §2-§3. Comportamiento de seguridad anclado en
data/corpus/08-seguridad-y-limites.md.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict

from coach.graph.state import Analysis, CoachState, RiskSignal
from coach.llm import get_chat_model

ANALYST_SYSTEM_PROMPT = """\
Eres el Analista de un coach de bienestar digital cuya filosofía es
"sustituir, no prohibir". Tu trabajo es analizar los patrones de uso de la
persona basándote ÚNICAMENTE en los datos que recibes (su perfil y sus datos de
uso). No inventes información que no esté en los datos, no consultes fuentes
externas ni conocimiento general (no usas RAG) y no diagnosticas.

Tarea de análisis. Produce un análisis estructurado con:
- patterns: patrones de uso relevantes observados en los datos (p. ej. picos en
  franjas concretas, concentración del tiempo en ciertas categorías).
- triggers: disparadores que parecen iniciar o sostener el uso, apoyándote en
  los triggers autoreportados y en lo que sugieran los datos.
- needs_covered: para cada uso significativo, la necesidad que probablemente
  cubría (descanso, conexión social, evasión, estimulación, etc.). Esto es el
  diferenciador del producto: entender qué aporta el uso para poder sustituirlo.

Seguridad (dominio sensible). Marca risk.flag=True, con un reason breve y
empático y una severity (LOW, MEDIUM o HIGH), solo si los datos sugieren alguna
de estas señales:
- malestar emocional persistente;
- uso que interfiere de forma seria con el sueño, el trabajo, la alimentación o
  las relaciones;
- sensación de no poder parar pese a quererlo;
- uso de la pantalla como única vía para soportar emociones difíciles.
Si no hay señales de este tipo, devuelve risk.flag=False, reason="" y
severity=NONE. No eres un profesional: nunca des consejo clínico, diagnósticos
ni nombres de fármacos o tratamientos.
"""


class _AnalystOutput(BaseModel):
    """Salida estructurada interna del nodo Analista.

    No forma parte del contrato compartido (`state.py`): solo agrupa los dos
    canales que produce el nodo en una única llamada al LLM.
    """

    model_config = ConfigDict(extra="forbid")

    analysis: Analysis
    risk: RiskSignal


def analyst(state: CoachState) -> CoachState:
    """Analiza `profile` + `usage` y emite `analysis` + `risk`.

    Guardia de entrada: si falta `profile` o `usage`, no llama al LLM y degrada
    de forma controlada escribiendo en el canal `errors`.
    """
    profile = state.get("profile")
    usage = state.get("usage")
    if profile is None or usage is None:
        return {"errors": ["analyst: falta profile/usage en el estado"]}

    user_content = (
        "Analiza los siguientes datos de la persona.\n\n"
        f"PERFIL (UserProfile):\n{profile.model_dump_json()}\n\n"
        f"DATOS DE USO (UsageData):\n{usage.model_dump_json()}"
    )
    messages = [
        SystemMessage(content=ANALYST_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    model = get_chat_model(temperature=0.2).with_structured_output(_AnalystOutput)
    result = model.invoke(messages)
    if not isinstance(result, _AnalystOutput):
        return {"errors": ["analyst: salida del LLM con formato inesperado"]}

    return {"analysis": result.analysis, "risk": result.risk}
