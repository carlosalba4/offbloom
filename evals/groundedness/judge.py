"""LLM-judge local para las métricas de DeepEval, sobre la capa LLM agnóstica.

Envuelve `coach.llm.get_chat_model()` en la interfaz `DeepEvalBaseLLM` para que
las métricas de DeepEval (p. ej. `FaithfulnessMetric`) puntúen con NUESTRO modelo
en lugar de con OpenAI. Por defecto eso es qwen3:8b vía Ollama (privacidad y
coste cero), pero es CONFIGURABLE por entorno sin tocar la suite: `LLM_PROVIDER`,
`OLLAMA_MODEL` o `API_MODEL` (ver `coach.config.settings`). Para usar un juez de
API basta cambiar esas variables; el código de la suite no cambia.

Detalle de la API de DeepEval (>=4.0): las métricas no llaman a `generate`
directamente con schema, sino a `generate_with_schema(prompt, schema=...)`, cuya
implementación base reenvía a `self.generate(prompt, schema=...)` y, si el
modelo no acepta el kwarg `schema`, reintenta sin él. Por eso `generate` aquí
acepta `schema` y, cuando viene, devuelve una instancia Pydantic vía
`with_structured_output`; cuando no, devuelve texto plano.
"""

from __future__ import annotations

from deepeval.models import DeepEvalBaseLLM
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel

from coach.config import settings
from coach.llm import get_chat_model


class LocalJudge(DeepEvalBaseLLM):
    """Juez de DeepEval respaldado por la capa LLM agnóstica del coach.

    Usa temperatura 0.0 para que el veredicto del juez sea lo más estable posible
    (aun así, un 8B es ruidoso: los números son una señal, no verdad absoluta).
    """

    def __init__(self) -> None:
        # Nota: no pasamos `model=` al super; cargamos el modelo en `load_model`.
        self._model: BaseChatModel = self.load_model()
        self.name = self.get_model_name()

    def load_model(self) -> BaseChatModel:
        """Devuelve el chat model agnóstico configurado, en modo determinista."""
        return get_chat_model(temperature=0.0)

    def generate(self, prompt: str, schema: type[BaseModel] | None = None) -> object:
        """Genera la respuesta del juez.

        Si `schema` viene, devuelve una instancia Pydantic de ese schema (vía
        salida estructurada); si no, devuelve el texto plano de la respuesta.
        """
        if schema is not None:
            return self._model.with_structured_output(schema).invoke(prompt)
        return self._model.invoke(prompt).content

    async def a_generate(self, prompt: str, schema: type[BaseModel] | None = None) -> object:
        """Variante async; delega en `generate` (el modelo local es síncrono)."""
        return self.generate(prompt, schema=schema)

    def get_model_name(self) -> str:
        """Nombre legible del juez, útil en los reportes de DeepEval."""
        backend = "ollama" if settings.llm_provider == "ollama" else settings.llm_provider
        model = settings.ollama_model if backend == "ollama" else settings.api_model
        return f"local-judge ({model} via {backend})"
