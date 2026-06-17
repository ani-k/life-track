"""
Core application settings using pydantic-settings.
All values are read from environment variables / .env file.
No hardcoded secrets — OWASP A02.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────
    app_name: str = "LifeTrack"
    debug: bool = False
    allowed_origins: list[str] = Field(default=["http://localhost:5173"])

    # ── Database ───────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/lifetrack",
        description="Async SQLAlchemy connection string",
    )

    # ── Auth ───────────────────────────────────────────────────────────
    secret_key: str = Field(min_length=32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ── LLM ───────────────────────────────────────────────────────────
    # LiteLLM model string — supports any provider prefix:
    #   "gpt-4o"                         → OpenAI
    #   "anthropic/claude-3-5-sonnet"    → Anthropic
    #   "ollama/llama3.1"                → local Ollama
    #   "openai/custom" + litellm_api_base → local LM Studio / LiteLLM proxy
    litellm_model: str = "gpt-4o"
    litellm_api_base: str | None = Field(
        default=None,
        description="Custom API base URL — use for local LLMs or a LiteLLM proxy tunnel",
    )
    litellm_api_key: str | None = Field(
        default=None,
        description="API key; optional for local providers",
    )
    openai_api_base: str | None = Field(
        default=None,
        description="Custom API base URL for OpenAI/proxy",
    )
    openai_api_key: str | None = Field(
        default=None,
        description="API key for OpenAI/proxy",
    )
    litellm_max_tokens: int = Field(default=2048, gt=0, le=128_000)
    litellm_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    litellm_max_retries: int = Field(default=3, ge=0, le=10)

    # ── Local LLM (Ollama) ─────────────────────────────────────────────
    # Default Ollama URL — override to point at a remote tunnel
    ollama_base_url: str = "http://localhost:11434"
    # Model served by Ollama — examples: "gemma3:2b", "llama3.1", "mistral"
    ollama_model: str = "gemma3:2b"

    @field_validator("secret_key")
    @classmethod
    def secret_key_not_example(cls, v: str) -> str:
        if "change-me" in v.lower():
            raise ValueError("SECRET_KEY must be changed from the example value in production")
        return v


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — call this everywhere."""
    return Settings()
