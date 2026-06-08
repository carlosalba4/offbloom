"""Provider-agnostic factory for the chat model and embeddings.

The rest of the codebase MUST NOT import a concrete model class. It calls
``get_chat_model()`` / ``get_embeddings()`` and the implementation is chosen
from ``settings.llm_provider``. Switching local <-> cloud is one env var
(LLM_PROVIDER). Imports are lazy so you only need the package for the provider
you actually use.
"""
from __future__ import annotations

from typing import Any

from coach.config import settings


def get_chat_model(**overrides: Any):
    """Return a LangChain chat model for the configured provider."""
    provider = settings.llm_provider.lower()
    params: dict[str, Any] = {"temperature": 0.3, **overrides}

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.ollama_model, base_url=settings.ollama_base_url, **params
        )
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=settings.api_model, api_key=settings.openai_api_key, **params)
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.api_model, google_api_key=settings.google_api_key, **params
        )
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.api_model, api_key=settings.anthropic_api_key, **params
        )

    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")


def get_embeddings():
    """Return the embeddings model (multilingual bge-m3 via Ollama by default)."""
    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(model=settings.embedding_model, base_url=settings.ollama_base_url)
