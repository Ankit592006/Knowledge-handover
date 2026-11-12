"""Application configuration management using Pydantic Settings (Render & Cloud Production Ready)."""

from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized, validated environment settings for the Knowledge Handover backend."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Knowledge Handover Platform"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    # Database (defaults to local SQLite for zero-friction local runs if PostgreSQL is not explicitly configured;
    # automatically normalizes Render's postgres:// or postgresql:// URLs to postgresql+psycopg://)
    DATABASE_URL: str = "sqlite:///./knowledge_handover_dev.db"

    # Security & Authentication
    JWT_SECRET_KEY: str = "dev_only_replace_with_32_byte_random_secret_key_012345"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Open-Source AI & RAG Configuration
    # Supported LLM_PROVIDER values: "ollama", "openai_compatible", "deterministic_extractive"
    # For Render / cloud hosting with open-source models (e.g. Groq, Together, OpenRouter, vLLM):
    # Set LLM_PROVIDER="openai_compatible", LLM_BASE_URL="https://api.groq.com/openai", LLM_API_KEY="gsk_..."
    LLM_PROVIDER: str = "ollama"
    LLM_BASE_URL: str = "http://localhost:11434"
    LLM_API_KEY: str = ""
    LLM_MODEL_NAME: str = "qwen2.5:7b-instruct"
    LLM_TIMEOUT_SECONDS: int = 45
    LLM_MAX_RETRIES: int = 2

    EMBEDDING_PROVIDER: str = "deterministic_hash"
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # RAG Chunking & Upload Limits
    CHUNK_SIZE_CHARS: int = 800
    CHUNK_OVERLAP_CHARS: int = 120
    MAX_UPLOAD_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB

    @property
    def normalized_database_url(self) -> str:
        """Normalize Render's postgres:// or postgresql:// connection strings to SQLAlchemy psycopg v3 driver."""
        url = self.DATABASE_URL.strip()
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://") and "+psycopg" not in url:
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def cors_origin_list(self) -> List[str]:
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        if "*" in origins:
            return ["*"]
        return origins

    @property
    def is_postgres(self) -> bool:
        return self.normalized_database_url.startswith("postgresql")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
