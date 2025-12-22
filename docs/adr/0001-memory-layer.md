# ADR-0001: Memory Layer Stack and Constraints

## Status
Accepted — Phase 1 implementation complete (memory layer, migrations, tracing).

## Context
- Phase 1 delivers the core memory layer with async SQLModel, asyncpg, pgvector, and OpenTelemetry tracing.
- Docker Compose provides PostgreSQL 15 (with pgvector) and Jaeger for local development and tests.
- Coverage gate is 80% (`pytest --cov=src --cov-fail-under=80`).

## Decision
- Use PostgreSQL + pgvector as the single datastore for relational and vector search.
- Use SQLModel with async SQLAlchemy/asyncpg for all DB operations (no sync code paths).
- Fix embedding dimension at 1536 in the initial migration with HNSW index (`m=16`, `ef_construction=64`) and GIN indexes on JSONB metadata.
- Instrument all MemoryManager operations with OpenTelemetry (`operation.type`, `operation.success`, `db.system=postgresql`, span attributes per method); 100% sampling; OTLP gRPC exporter by default, in-memory exporter when `otel_exporter_otlp_endpoint="memory"`.
- Auto-create sessions in `store_message` with `user_id="auto-created"` when missing; enforce trimmed, non-empty content and valid roles.
- Support semantic search with cosine ordering, metadata filters, date filters, and timing metrics; `temporal_query` enforces start/end validation.
- Provide health check that queries Postgres and pgvector versions and records span attributes.

## Consequences
- Changing `vector_dimension` requires a new migration to keep schema and settings aligned; current migration hardcodes `Vector(1536)`.
- Infra dependency: Postgres 15 + pgvector and Jaeger must be running for integration tests.
- All DB access must remain async to preserve compliance with the architecture and tracing guarantees.
- Session auto-creation means callers get implicit sessions unless they pre-create them; downstream code should account for `user_id="auto-created"` defaults.

