"""Central settings, loaded from env / .env. Nothing is hardcoded elsewhere."""

from __future__ import annotations

from pydantic import field_validator
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

    # Persistencia (SQLite en desarrollo; migrable a Postgres sin reescritura)
    database_url: str = "sqlite:///./offbloom.db"

    # Autenticación JWT (ADR-007). jwt_secret_key es obligatorio: sin default
    # para forzar su configuración explícita en cada entorno (dev/CI/prod).
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    @field_validator("jwt_secret_key")
    @classmethod
    def _validate_jwt_secret_key_length(cls, v: str) -> str:
        """Exige un secreto suficientemente largo (>=32 bytes) para HS256."""
        if len(v.encode()) < 32:
            raise ValueError(
                "JWT_SECRET_KEY debe tener al menos 32 bytes; genera uno con: "
                'python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        return v

    # Login con Google (OIDC, ADR-009). Los dos secretos son opcionales a
    # propósito: sin ellos la app arranca igual (CI y tests no necesitan
    # credenciales reales) y solo /auth/google/login responde 503.
    # OJO: google_client_id/secret son de OAuth, NO son google_api_key (Gemini).
    google_client_id: str | None = None
    google_client_secret: str | None = None
    # Debe coincidir EXACTAMENTE con la URI registrada en Google Cloud Console.
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    # Ruta del frontend a la que vuelve el navegador tras el callback; se
    # concatena con frontend_origin para no duplicar el origen en dos settings.
    google_post_login_path: str = "/auth/google/callback"

    # Cookie del refresh token (transporte httpOnly, cross-origin directo).
    cookie_refresh_name: str = "offbloom_refresh"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None
    cookie_path: str = "/auth"
    # Cookie efímera que transporta el `state` anti-CSRF del flujo OAuth entre
    # /auth/google/login y /auth/google/callback (double-submit, ADR-009).
    cookie_oauth_state_name: str = "offbloom_oauth_state"
    oauth_state_expire_seconds: int = 600
    # Origen del frontend, usado para restringir CORS (allow_credentials=True
    # exige un origen explícito; nunca "*").
    frontend_origin: str = "http://localhost:3000"

    @field_validator("cookie_samesite")
    @classmethod
    def _validate_cookie_samesite(cls, v: str) -> str:
        """Normaliza a minúsculas y exige un valor válido para el atributo SameSite."""
        normalized = v.lower()
        valid_values = {"lax", "strict", "none"}
        if normalized not in valid_values:
            raise ValueError(f"COOKIE_SAMESITE debe ser uno de {sorted(valid_values)}")
        return normalized

    # Observability (optional)
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    @property
    def google_post_login_url(self) -> str:
        """URL del frontend a la que vuelve el navegador tras el callback de Google."""
        return f"{self.frontend_origin.rstrip('/')}{self.google_post_login_path}"


settings = Settings()
