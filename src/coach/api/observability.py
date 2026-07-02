"""Helper de observabilidad para las llamadas al grafo del coach.

Import perezoso de Langfuse: si las claves no están configuradas o el import
falla, degrada a lista vacía sin romper la request.
"""

from __future__ import annotations

import logging

from coach.config import settings

logger = logging.getLogger(__name__)


def langfuse_callbacks() -> list:
    """Devuelve [CallbackHandler] si las claves de Langfuse están configuradas.

    Usa import perezoso y captura cualquier error de import o construcción para
    degradar a lista vacía sin romper la request.
    """
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return []

    try:
        from langfuse.langchain import CallbackHandler  # noqa: PLC0415

        handler = CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        return [handler]
    except Exception as exc:  # noqa: BLE001
        # Langfuse no disponible o mal configurado — el coach sigue sin trazas.
        logger.warning("Langfuse no disponible, trazas desactivadas: %s", exc)
        return []
