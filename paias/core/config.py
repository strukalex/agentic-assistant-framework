"""Core application configuration for the PAIAS backend.

Defines a typed Settings object backed by environment variables (and .env files)
for database, observability, and vector-search related parameters.
"""

from __future__ import (
    annotations,
)  # Allow postponed evaluation of annotations (Python typing nicety)

from pydantic import Field  # Used to declare typed fields with metadata and validation
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,  # Pydantic Settings config helper
)


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables."""

    # Pydantic Settings configuration:
    # - env_file: load variables from a local .env file for development
    # - env_file_encoding: read .env as UTF-8
    # - extra="ignore": ignore any env vars that don't correspond to defined fields
    # - populate_by_name: allow using both field name and alias for env var population
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # ----------------------
    # Database configuration
    # ----------------------

    # Async PostgreSQL URL used by SQLAlchemy with asyncpg.
    # Can be overridden by setting the env var PAIAS_DATABASE_URL.
    # Note: Separate from Windmill's DATABASE_URL to avoid conflicts in containerized environments.
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/paias",
        description="Async PostgreSQL connection string with asyncpg driver",
        alias="PAIAS_DATABASE_URL",
    )

    # Base size of the async SQLAlchemy connection pool.
    # Tune this based on concurrent load and DB capacity.
    database_pool_size: int = Field(
        default=5,
        description="SQLAlchemy async engine pool size (asyncpg)",
    )

    # How many extra connections beyond pool_size are allowed under load.
    # Useful for handling occasional spikes without raising errors immediately.
    database_max_overflow: int = Field(
        default=10,
        description="Maximum overflow connections for async engine pool",
    )

    # ----------------------
    # OpenTelemetry / tracing
    # ----------------------

    # Endpoint where OTLP traces/metrics are sent, typically Jaeger/OTel collector.
    # Example: http://localhost:4317 for local Jaeger.
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4317",
        description="OTLP endpoint for trace export (Jaeger collector)",
    )

    # Separate endpoint for traces (optional, falls back to otel_exporter_otlp_endpoint)
    otel_exporter_otlp_traces_endpoint: str | None = Field(
        default=None,
        description="OTLP endpoint for traces (defaults to otel_exporter_otlp_endpoint)",
    )

    # Endpoint where OTLP logs are sent, typically Loki.
    # Example: http://localhost:3100/otlp/v1/logs for local Loki.
    otel_exporter_otlp_logs_endpoint: str | None = Field(
        default=None,
        description="OTLP endpoint for log export (Loki). If set, logs are exported via OTLP.",
    )

    # Logical service name that will appear in tracing backends (Jaeger, etc.).
    # Helps distinguish this component from others in a distributed system.
    otel_service_name: str = Field(
        default="paias",  # Updated to match agent layer per Constitution Article II.H
        description="OpenTelemetry service.name resource attribute",
    )

    # Fraction of requests to sample for tracing, between 0.0 and 1.0.
    # 1.0 = trace everything (good for dev), lower values reduce overhead in prod.
    otel_sampling_rate: float = Field(
        default=1.0,
        ge=0.0,  # Pydantic validation: minimum 0.0
        le=1.0,  # Pydantic validation: maximum 1.0
        description="Trace sampling rate (0.0-1.0); 1.0 for always on",
    )

    # ----------------------
    # MCP / web search configuration
    # ----------------------
    websearch_engine: str = Field(
        default="google",
        description="Search engine for Open-WebSearch MCP server",
    )
    websearch_max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum results returned by web_search tool",
    )
    websearch_timeout: int = Field(
        default=30,
        ge=1,
        le=120,
        description="Timeout (seconds) for MCP tool calls (WEBSEARCH_TIMEOUT)",
    )

    # ------------------------------------------------
    # Vector / pgvector configuration for embeddings
    # ------------------------------------------------

    # Dimension of embedding vectors stored in pgvector columns.
    # Must match the embedding model you use (e.g. 1536 for some OpenAI models).
    vector_dimension: int = Field(
        default=1536,
        description="Embedding dimension for pgvector columns",
    )

    # HNSW ef_search parameter for pgvector ANN queries.
    # Higher values typically improve recall at the cost of query latency.
    hnsw_ef_search: int = Field(
        default=40,
        description="HNSW ef_search parameter for pgvector queries",
    )

    # ----------------------
    # Embedding model info
    # ----------------------
    embedding_model_name: str = Field(
        default="text-embedding-ada-002",
        description="Embedding model identifier; dimension follows model defaults",
    )

    # ----------------------
    # Logging configuration
    # ----------------------
    enable_agentic_logging: bool = Field(
        default=False,
        description="Enable detailed agentic loop logging (shows LLM conversation messages and tool calls). Set ENABLE_AGENTIC_LOGGING=true to enable.",
    )
    agentic_logging_verbose: bool = Field(
        default=False,
        description="When true, log full JSON payloads. When false, log clean conversation chain format. Set AGENTIC_LOGGING_VERBOSE=true for full JSON.",
    )

    # ----------------------
    # Windmill integration
    # ----------------------
    windmill_base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL for the Windmill instance handling workflow runs",
    )
    windmill_workspace: str = Field(
        default="default",
        description="Windmill workspace name used for workflow invocations",
    )
    windmill_token: str | None = Field(
        default=None,
        description="Windmill API token for authenticated requests (if required)",
    )
    windmill_flow_path: str = Field(
        default="research/daily_research",
        description="Path to the DailyTrendingResearch flow in Windmill (without f/ prefix)",
    )
    approval_timeout_seconds: int = Field(
        default=300,
        ge=1,
        le=900,
        description="Default approval timeout in seconds (target: 5 minutes ±10s)",
    )


# Instantiate a global settings object.
# Import this in your app as `from config import settings` and use `settings.<field>`.
settings = Settings()
