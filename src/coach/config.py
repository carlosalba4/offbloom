"""Central settings, loaded from env / .env. Nothing is hardcoded elsewhere."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Which LLM backend to use: "ollama" (local) or "openai"/"google"/"anthropic" (cloud)
    llm_provider: str = "ollama"

    # Local (Ollama)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    # Cloud API (used when llm_provider != "ollama")
    api_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    google_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Embeddings (multilingual, served locally by Ollama)
    embedding_model: str = "bge-m3"

    # Vector store
    chroma_dir: str = "./.chroma"
    corpus_dir: str = "./data/corpus"

    # Observability (optional)
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"


settings = Settings()
