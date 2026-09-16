"""
Configuracion centralizada del proyecto, cargada desde variables de entorno
(directamente o via el archivo .env) usando pydantic-settings.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Selector de proveedor: "openai", "anthropic" u "openrouter"
    llm_provider: Literal["openai", "anthropic", "openrouter"] = "anthropic"

    # OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # Anthropic
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # OpenRouter (proxy OpenAI-compatible hacia múltiples modelos/proveedores)
    openrouter_api_key: str | None = None
    openrouter_model: str = "anthropic/claude-3.5-haiku"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Opcionales, recomendados por OpenRouter para rankings/analytics.
    openrouter_site_url: str | None = None
    openrouter_site_name: str | None = None

    # App
    app_name: str = "Estimador CAG"
    app_env: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Devuelve una instancia cacheada de Settings (se lee el .env una sola vez)."""
    return Settings()
