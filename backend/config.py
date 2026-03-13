"""
Application Configuration
Pydantic Settings for environment-based configuration with multi-LLM support.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve path to the project root .env (one level up from backend/)
_ENV_FILE = str(Path(__file__).resolve().parent.parent / ".env")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # ==========================================================================
    # Application
    # ==========================================================================
    app_name: str = "SAP App Builder"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    secret_key: str = "dev-secret-key-change-in-production"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:8000"
    
    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    # ==========================================================================
    # Database
    # ==========================================================================
    database_url: str = "sqlite+aiosqlite:///./sap_builder.db"
    
    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.database_url
    
    # ==========================================================================
    # LLM Providers
    # ==========================================================================
    # API Keys
    openai_api_key: str | None = None
    google_api_key: str | None = None
    deepseek_api_key: str | None = None
    kimi_api_key: str | None = None
    xai_api_key: str | None = None
    openrouter_api_key: str | None = None
    
    # Default provider
    default_llm_provider: Literal["openai", "gemini", "deepseek", "kimi", "xai", "openrouter"] = "xai"
    default_llm_model: str = "grok-4-1-fast-reasoning"
    
    # Model mappings per provider
    @property
    def llm_models(self) -> dict[str, str]:
        return {
            "openai": self.default_llm_model if self.default_llm_provider == "openai" else "gpt-4o-mini",
            "gemini": self.default_llm_model if self.default_llm_provider == "gemini" else "gemini-1.5-pro",
            "deepseek": self.default_llm_model if self.default_llm_provider == "deepseek" else "deepseek-chat",
            "kimi": self.default_llm_model if self.default_llm_provider == "kimi" else "moonshot-v1-128k",
            "xai": self.default_llm_model if self.default_llm_provider == "xai" else "grok-4-1-fast-reasoning",
            "openrouter": self.default_llm_model if self.default_llm_provider == "openrouter" else "openai/gpt-4.1",
        }
    
    def get_api_key(self, provider: str) -> str | None:
        """Get API key for a specific provider."""
        key_map = {
            "openai": self.openai_api_key,
            "gemini": self.google_api_key,
            "deepseek": self.deepseek_api_key,
            "kimi": self.kimi_api_key,
            "xai": self.xai_api_key,
            "openrouter": self.openrouter_api_key,
        }
        return key_map.get(provider)
    
    @property
    def available_providers(self) -> list[str]:
        """List of providers with configured API keys."""
        providers = []
        if self.openai_api_key:
            providers.append("openai")
        if self.google_api_key:
            providers.append("gemini")
        if self.deepseek_api_key:
            providers.append("deepseek")
        if self.kimi_api_key:
            providers.append("kimi")
        if self.xai_api_key:
            providers.append("xai")
        if self.openrouter_api_key:
            providers.append("openrouter")
        return providers
    
    # ==========================================================================
    # Storage Paths
    # ==========================================================================
    artifacts_path: str = "./artifacts"
    templates_path: str = "./backend/templates"

    # ==========================================================================
    # Production Settings
    # ==========================================================================
    # API key for builder access (leave empty for open access in dev)
    api_key: str | None = None

    # Rate limiting (requests per minute per IP)
    rate_limit_rpm: int = 60
    rate_limit_burst: int = 10

    # Redis for caching/rate limiting (optional)
    redis_url: str | None = None

    # Logging
    log_format: Literal["text", "json"] = "text"
    log_level: str = "INFO"

    # File size limits
    max_generation_size_mb: int = 50

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
