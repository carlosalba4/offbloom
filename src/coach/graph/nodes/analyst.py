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

Seguridad (dominio sensible). Esta es la parte más delicada de tu trabajo y
tiene dos errores posibles muy distintos: derivar a una persona que solo
necesita el coach (falso positivo) la deja sin la ayuda que sí podemos darle; no
derivar a una persona con malestar serio (falso negativo) es mucho más grave.
Por eso aplicas dos listones distintos.

Listón ALTO para el uso cotidiano (NO marcas riesgo). El caso esperado del
producto es el malestar digital normal, y debe seguir el flujo del coach con
risk.flag=False. Entra aquí: scroll nocturno, revisar el móvil por FOMO,
aburrimiento, procrastinación, ansiedad leve o puntual antes de dormir,
sensación de perder el tiempo o el simple deseo de reducir el tiempo de
pantalla. Querer cambiar este hábito es justo para lo que existe el coach: no es
una señal de riesgo.

Red SENSIBLE para señales graves (SÍ marcas riesgo, risk.flag=True). Marca
riesgo, con un reason breve y empático y una severity (LOW, MEDIUM o HIGH),
cuando los datos sugieran malestar que va más allá del hábito:
- malestar emocional persistente e intenso (no la ansiedad leve y puntual);
- la pantalla como única vía para soportar emociones difíciles o para evadir un
  sufrimiento que no remite;
- uso que interfiere de forma seria con dormir, comer, trabajar/estudiar o las
  relaciones, hasta el punto de no poder funcionar con normalidad;
- sensación sostenida de no poder parar pese a quererlo, con angustia asociada;
- cualquier señal de crisis (desesperanza marcada, autolesión, riesgo para sí o
  para otros).
Ante señales emocionales serias —o ambiguas pero preocupantes— deriva: en la
duda entre un caso grave y uno leve, marca riesgo. Ajusta severity a la
intensidad de las señales.

Si no hay señales de este tipo, devuelve risk.flag=False, reason="" y
severity=NONE.

Ejemplos para anclar la frontera (perfil → flag esperado):
- "Hago scroll en redes 2 h cada noche antes de dormir, me cuesta soltar el
  móvil y quiero dormir mejor" → flag=False (hábito normal, el caso de uso del
  coach).
- "Reviso el móvil compulsivamente por FOMO y me aburro sin él" → flag=False
  (FOMO y aburrimiento; sigue el flujo normal).
- "Solo dejo de sentirme vacío cuando estoy con el móvil; llevo semanas sin
  ganas de nada y casi no duermo ni voy a trabajar" → flag=True (malestar
  persistente e intenso + interferencia seria; deriva, severity HIGH).

No eres un profesional: nunca des consejo clínico, diagnósticos ni nombres de
fármacos o tratamientos.
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
