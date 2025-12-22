from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/paias",
        description="Async PostgreSQL connection string with asyncpg driver",
    )
    database_pool_size: int = Field(
        default=5, description="SQLAlchemy async engine pool size (asyncpg)"
    )
    database_max_overflow: int = Field(
        default=10, description="Maximum overflow connections for async engine pool"
    )

    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4317",
        description="OTLP endpoint for trace export (Jaeger collector)",
    )
    otel_service_name: str = Field(
        default="paias-memory-layer", description="OpenTelemetry service.name resource attribute"
    )
    otel_sampling_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Trace sampling rate (0.0-1.0); 1.0 for always on",
    )

    vector_dimension: int = Field(
        default=1536, description="Embedding dimension for pgvector columns"
    )
    hnsw_ef_search: int = Field(
        default=40, description="HNSW ef_search parameter for pgvector queries"
    )


settings = Settings()

