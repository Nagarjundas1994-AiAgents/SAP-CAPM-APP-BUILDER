"""
Application Configuration
Pydantic Settings for environment-based configuration with multi-LLM support.
"""

from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
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
    
    # Default provider
    default_llm_provider: Literal["openai", "gemini", "deepseek", "kimi"] = "openai"
    default_llm_model: str = "gpt-4-turbo-preview"
    
    # Model mappings per provider
    @property
    def llm_models(self) -> dict[str, str]:
        return {
            "openai": self.default_llm_model if self.default_llm_provider == "openai" else "gpt-4-turbo-preview",
            "gemini": "gemini-1.5-pro",
            "deepseek": "deepseek-chat",
            "kimi": "moonshot-v1-128k",
        }
    
    def get_api_key(self, provider: str) -> str | None:
        """Get API key for a specific provider."""
        key_map = {
            "openai": self.openai_api_key,
            "gemini": self.google_api_key,
            "deepseek": self.deepseek_api_key,
            "kimi": self.kimi_api_key,
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
        return providers
    
    # ==========================================================================
    # Storage Paths
    # ==========================================================================
    artifacts_path: str = "./artifacts"
    templates_path: str = "./backend/templates"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
