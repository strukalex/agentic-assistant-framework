# Research: Core Foundation and Memory Layer

**Feature**: Core Foundation and Memory Layer  
**Date**: 2025-12-21  
**Purpose**: Resolve technical unknowns and establish implementation decisions

## Overview

This document consolidates research findings for implementing the Core Foundation and Memory Layer. All technical decisions below are informed by best practices, constitutional requirements, and Phase 1 constraints.

---

## 1. SQLModel + pgvector Integration

### Decision

Use SQLModel 0.0.14+ with custom SQLAlchemy Column for pgvector types. Dimension is read from settings (`vector_dimension`) with default 1536 (OpenAI Ada-002), so switching models only requires config + migration.

### Rationale

- **SQLModel** provides unified Pydantic + SQLAlchemy models (single source of truth)
- **pgvector** requires SQLAlchemy Column syntax: `Field(sa_column=Column(Vector(1536)))`
- This approach maintains type safety while supporting PostgreSQL-specific vector operations

### Implementation Pattern

```python
from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from pgvector.sqlalchemy import Vector

class Document(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    content: str
    embedding: Optional[list[float]] = Field(
        sa_column=Column(Vector(1536)),
        default=None
    )
    metadata_: dict = Field(sa_column=Column(JSON), default_factory=dict)
```

### Alternatives Considered

1. **Pure SQLAlchemy**: More verbose; loses Pydantic validation at model definition
2. **Pydantic + manual SQL**: No ORM benefits; requires hand-written queries
3. **LangChain's vector stores**: Too opinionated; doesn't integrate with SQLModel

### References

- SQLModel docs: https://sqlmodel.tiangolo.com/
- pgvector-python: https://github.com/pgvector/pgvector-python
- SQLAlchemy Vector type: `pgvector.sqlalchemy.Vector`

---

## 2. Async Database Driver Configuration

### Decision

Use `asyncpg` as the async PostgreSQL driver with SQLAlchemy's async engine.

### Rationale

- **asyncpg** is the fastest async PostgreSQL driver for Python (10x faster than psycopg2)
- Native support in SQLAlchemy 2.0+ via `create_async_engine()`
- Required for async/await patterns mandated by Constitution Article III.B

### Implementation Pattern

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:5432/paias"

engine = create_async_engine(DATABASE_URL, echo=True, future=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
```

### Connection Pooling

- Default pool size: 5 connections (asyncpg default)
- Max overflow: 10 connections
- Pool recycle: 3600 seconds (1 hour)
- Phase 1 uses defaults; Phase 2 will tune based on load testing

### Alternatives Considered

1. **psycopg3 async**: Newer but less mature than asyncpg
2. **Sync driver with thread pool**: Violates async-first principle (Article III.B)

### References

- asyncpg docs: https://magicstack.github.io/asyncpg/
- SQLAlchemy async: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

---

## 3. OpenTelemetry Instrumentation Strategy

### Decision

Use custom decorators (`@trace_memory_operation`) with manual span creation for fine-grained control.

### Rationale

- **Manual spans** provide precise control over attributes (query parameters, result counts)
- **Auto-instrumentation** (SQLAlchemy tracer) captures low-level queries but lacks business context
- Hybrid approach: manual spans for MemoryManager methods + auto-instrumentation for underlying queries

### Implementation Pattern

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

tracer = trace.get_tracer("paias.memory", "1.0.0")

def trace_memory_operation(operation_name: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(f"memory.{operation_name}") as span:
                span.set_attribute("operation.type", operation_name)
                # Add method-specific attributes
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("operation.success", True)
                    return result
                except Exception as e:
                    span.set_attribute("operation.success", False)
                    span.record_exception(e)
                    raise
        return wrapper
    return decorator
```

### Jaeger Configuration

- **Exporter**: OTLP gRPC (standard protocol)
- **Endpoint**: `http://localhost:4317` (Jaeger OTLP receiver)
- **Sampling**: 100% for Phase 1 (AlwaysOnSampler)
- **Service name**: `paias-memory-layer`

### Span Attributes

Standard attributes for all memory operations:
- `operation.type`: store_document, semantic_search, etc.
- `operation.success`: boolean
- `db.system`: postgresql
- `db.statement`: SQL query (sanitized, no sensitive data)
- `db.rows_affected`: number of rows returned/modified

### Alternatives Considered

1. **Logfire**: Pydantic-native but adds another service dependency
2. **Langfuse**: Agent-specific; not suitable for infrastructure layer
3. **AWS X-Ray**: Cloud-specific; violates platform independence

### References

- OpenTelemetry Python: https://opentelemetry.io/docs/languages/python/
- Jaeger OTLP: https://www.jaegertracing.io/docs/1.50/apis/#otlp

---

## 4. pgvector Index Selection

### Decision

Use **HNSW index** for vector similarity search (Phase 1).

### Rationale

- **HNSW** (Hierarchical Navigable Small World) provides better query performance than IVFFlat for datasets <100k vectors
- Lower maintenance overhead (no need to rebuild after inserts)
- Better recall at high speed for exact queries

### Index Creation

```sql
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Parameters**:
- `m = 16`: Number of connections per layer (balance between build time and query speed)
- `ef_construction = 64`: Size of dynamic candidate list (higher = better recall during build)

### Query Configuration

```sql
SET hnsw.ef_search = 40;  -- Dynamic candidate list size for queries (higher = better recall)
```

### IVFFlat Comparison

| Metric | HNSW | IVFFlat |
|--------|------|---------|
| Build time | Slower | Faster |
| Query speed | Faster | Slower (at scale) |
| Insert performance | Good | Requires periodic reindex |
| Best for | <100k vectors, frequent inserts | >1M vectors, batch workloads |

**Decision**: HNSW is Phase 1 default. Migrate to IVFFlat if dataset exceeds 100k documents AND query patterns are batch-oriented.

### Alternatives Considered

1. **IVFFlat**: Faster build, slower queries; better for batch workloads
2. **No index**: Unacceptable performance for semantic search (full table scan)

### References

- pgvector indexing: https://github.com/pgvector/pgvector#indexing
- HNSW algorithm: https://arxiv.org/abs/1603.09320

---

## 5. Alembic Migration Strategy

### Decision

Use Alembic with async SQLAlchemy engine for schema migrations.

### Rationale

- **Alembic** is the de-facto standard for SQLAlchemy migrations
- Async support available via `run_async()` in migration scripts
- Integrates seamlessly with SQLModel (which uses SQLAlchemy under the hood)

### Initial Migration Tasks

1. Enable pgvector extension: `CREATE EXTENSION IF NOT EXISTS vector;`
2. Create `sessions` table with UUID primary key
3. Create `messages` table with foreign key to sessions
4. Create `documents` table with vector column
5. Create indexes: HNSW on embeddings, GIN on JSONB metadata, B-tree on session_id

### Migration Script Template

```python
"""Initial schema with pgvector

Revision ID: 001
Revises: 
Create Date: 2025-12-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    
    # Create sessions table
    op.create_table(
        "sessions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("metadata_", JSONB, nullable=True),
    )
    
    # Create messages table
    # ... (similar structure)
    
    # Create documents table with vector column
    op.create_table(
        "documents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("metadata_", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    
    # Create indexes
    op.create_index("idx_documents_embedding_hnsw", "documents", ["embedding"], 
                    postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"},
                    postgresql_with={"m": 16, "ef_construction": 64})
    op.create_index("idx_documents_metadata_gin", "documents", ["metadata_"], 
                    postgresql_using="gin")

def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.execute("DROP EXTENSION IF EXISTS vector")
```

### Rollback Testing

- All migrations MUST have both `upgrade()` and `downgrade()` functions
- CI tests verify: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head`
- No data loss allowed during rollback (schema-only changes in Phase 1)

### Alternatives Considered

1. **Raw SQL scripts**: No version tracking; error-prone
2. **SQLModel.metadata.create_all()**: No migration history; can't rollback
3. **Flyway/Liquibase**: JVM-based; incompatible with Python-first stack

### References

- Alembic docs: https://alembic.sqlalchemy.org/
- Async migrations: https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic

---

## 6. Environment Configuration

### Decision

Use Pydantic Settings for type-safe environment variable management.

### Rationale

- **Pydantic Settings** provides validation, type coercion, and default values
- Integrates with `.env` files via `python-dotenv`
- Constitutional requirement for environment-based configuration (Article III.F)

### Implementation Pattern

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/paias"
    database_pool_size: int = 5
    database_max_overflow: int = 10
    
    # OpenTelemetry
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "paias-memory-layer"
    otel_sampling_rate: float = 1.0  # 100% for Phase 1
    
    # Vector Search
    vector_dimension: int = 1536
    hnsw_ef_search: int = 40

settings = Settings()
```

### .env.example

```bash
# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/paias
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10

# OpenTelemetry Configuration
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=paias-memory-layer
OTEL_SAMPLING_RATE=1.0

# Vector Search Configuration
VECTOR_DIMENSION=1536
HNSW_EF_SEARCH=40
```

### Alternatives Considered

1. **os.environ directly**: No validation; error-prone
2. **ConfigParser**: Outdated; no type safety
3. **python-decouple**: Less feature-rich than Pydantic Settings

### References

- Pydantic Settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/

---

## 7. Docker Compose Infrastructure

### Decision

Use Docker Compose with PostgreSQL + pgvector pre-installed image and Jaeger all-in-one.

### Rationale

- **ankane/pgvector image**: Official PostgreSQL image with pgvector extension pre-compiled
- **jaegertracing/all-in-one**: Single container for development (collector + query + UI)
- Simplifies local development (single `docker-compose up` command)

### docker-compose.yml

```yaml
version: '3.8'

services:
  postgres:
    image: ankane/pgvector:latest
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: paias
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  jaeger:
    image: jaegertracing/all-in-one:latest
    environment:
      COLLECTOR_OTLP_ENABLED: true
    ports:
      - "16686:16686"  # Jaeger UI
      - "4317:4317"    # OTLP gRPC receiver
      - "4318:4318"    # OTLP HTTP receiver
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:16686"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### Usage

```bash
# Start infrastructure
docker-compose up -d

# Check health
docker-compose ps

# View logs
docker-compose logs -f postgres
docker-compose logs -f jaeger

# Stop and remove volumes
docker-compose down -v
```

### Alternatives Considered

1. **Separate PostgreSQL + pgvector install**: More complex setup; error-prone
2. **Managed services (RDS, Jaeger Cloud)**: Adds cloud dependency; violates local-first Phase 1
3. **Kubernetes**: Overkill for Phase 1; complexity not justified

### References

- pgvector Docker image: https://hub.docker.com/r/ankane/pgvector
- Jaeger Docker: https://www.jaegertracing.io/docs/1.50/getting-started/

---

## 8. Session Lifecycle Management

### Decision

**Sessions are auto-created** when the first message is stored (implicit session creation).

### Rationale

- Simplifies agent code (no explicit session.create() call required)
- Matches conversational UX (sessions start when user sends first message)
- Explicit session creation can be added in Phase 2 if needed

### Implementation Pattern

```python
async def store_message(
    self, session_id: UUID, role: str, content: str, metadata: dict | None = None
) -> UUID:
    """Store a message and auto-create session if it doesn't exist."""
    async with self.get_session() as db:
        # Check if session exists
        session = await db.get(Session, session_id)
        if not session:
            # Auto-create session
            session = Session(id=session_id, user_id="default", created_at=datetime.utcnow())
            db.add(session)
        
        # Create message
        message = Message(
            id=uuid4(),
            session_id=session_id,
            role=role,
            content=content,
            metadata_=metadata or {},
            created_at=datetime.utcnow()
        )
        db.add(message)
        await db.commit()
        return message.id
```

### Explicit Session Creation (Future)

If Phase 2 requires explicit session management:

```python
async def create_session(self, user_id: str, metadata: dict | None = None) -> UUID:
    """Explicitly create a new session."""
    async with self.get_session() as db:
        session = Session(
            id=uuid4(),
            user_id=user_id,
            metadata_=metadata or {},
            created_at=datetime.utcnow()
        )
        db.add(session)
        await db.commit()
        return session.id
```

### Alternatives Considered

1. **Explicit session creation required**: More boilerplate for agents
2. **Sessions never expire**: Acceptable for Phase 1; retention policies deferred to Phase 2

### References

- Design pattern: "Convention over configuration" principle

---

## 9. Test Strategy

### Decision

Use pytest with pytest-asyncio for async test support and pytest-docker for container orchestration.

### Rationale

- **pytest-asyncio**: Native async/await support in test functions
- **pytest-docker**: Spin up PostgreSQL + Jaeger containers during test execution
- **Fixtures**: Reusable database session, sample data, and embeddings

### Test Coverage Targets (Article III.A)

| Component | Target Coverage | Strategy |
|-----------|----------------|----------|
| MemoryManager | 90%+ | Unit + integration tests |
| Telemetry decorators | 85%+ | Unit tests with mock tracer |
| Pydantic models | 95%+ | Validation edge cases |
| Migrations | 80%+ | Up/down rollback tests |
| Overall | ≥80% | CI enforcement |

### Test Structure

```python
# tests/conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    return "docker-compose.test.yml"

@pytest.fixture(scope="session")
async def db_engine(docker_services):
    """Wait for PostgreSQL to be ready, return async engine."""
    docker_services.wait_until_responsive(
        timeout=30.0,
        pause=0.5,
        check=lambda: check_postgres_ready()
    )
    engine = create_async_engine("postgresql+asyncpg://postgres:postgres@localhost:5432/test_paias")
    yield engine
    await engine.dispose()

@pytest.fixture
async def db_session(db_engine):
    """Provide a clean database session for each test."""
    async with AsyncSession(db_engine) as session:
        yield session
        await session.rollback()

# tests/integration/test_semantic_search.py
@pytest.mark.asyncio
async def test_semantic_search_returns_relevant_documents(memory_manager, sample_documents):
    """Given 100 documents, when querying 'async programming', then relevant docs returned."""
    # Arrange: Insert sample documents
    for doc in sample_documents:
        await memory_manager.store_document(doc.content, doc.metadata, doc.embedding)
    
    # Act: Perform semantic search
    results = await memory_manager.semantic_search("async programming benefits", top_k=5)
    
    # Assert: Top results are about async programming
    assert len(results) == 5
    assert "async" in results[0].content.lower() or "asyncio" in results[0].content.lower()
```

### Continuous Integration

```yaml
# .github/workflows/ci.yml (example)
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest --cov=src --cov-fail-under=80 tests/
```

### Alternatives Considered

1. **unittest**: Less Pythonic than pytest; no native async support
2. **Manual Docker management**: Slower; requires developers to start services manually
3. **In-memory SQLite**: Doesn't support pgvector; incompatible with production schema

### References

- pytest-asyncio: https://pytest-asyncio.readthedocs.io/
- pytest-docker: https://github.com/avast/pytest-docker

---

## 10. Embedding Validation Strategy

### Decision

Validate embedding dimension (1536) at Pydantic model level before database insertion.

### Rationale

- **Early validation**: Catch dimension mismatches before expensive database operations
- **Clear error messages**: Pydantic validation errors are developer-friendly
- **Type safety**: Ensures all embeddings conform to OpenAI Ada-002 format

### Implementation Pattern

```python
from pydantic import field_validator

class DocumentCreate(BaseModel):
    content: str
    embedding: list[float]
    metadata: dict = Field(default_factory=dict)
    
    @field_validator("embedding")
    @classmethod
    def validate_embedding_dimension(cls, v: list[float]) -> list[float]:
        if len(v) != 1536:
            raise ValueError(f"Embedding must be 1536-dimensional, got {len(v)}")
        return v
    
    @field_validator("embedding")
    @classmethod
    def validate_embedding_values(cls, v: list[float]) -> list[float]:
        if not all(isinstance(x, (int, float)) for x in v):
            raise ValueError("Embedding must contain only numeric values")
        return v
```

### Edge Case Handling

1. **Empty embedding list**: Validation error before DB insertion
2. **Wrong dimension (e.g., 768 for BERT)**: Validation error with clear message
3. **Non-numeric values**: Pydantic coercion + validation
4. **Null/None embedding**: Allowed (optional field) for documents without embeddings

### Alternatives Considered

1. **Database constraint validation**: Fails late; expensive rollback
2. **No validation**: Silent failures; corrupt data
3. **Separate validation service**: Overkill for Phase 1

### References

- Pydantic field validators: https://docs.pydantic.dev/latest/concepts/validators/

---

## Summary of Key Decisions

| Topic | Decision | Rationale |
|-------|----------|-----------|
| **ORM** | SQLModel with pgvector Column | Unified Pydantic + SQLAlchemy models |
| **Driver** | asyncpg | Fastest async PostgreSQL driver |
| **Tracing** | Custom OpenTelemetry decorators | Fine-grained control over span attributes |
| **Vector Index** | HNSW | Better query performance for <100k vectors |
| **Migrations** | Alembic | Standard SQLAlchemy migration tool |
| **Config** | Pydantic Settings | Type-safe environment variables |
| **Docker** | PostgreSQL + Jaeger in Compose | Single-command local development |
| **Sessions** | Auto-created on first message | Simplifies agent code |
| **Testing** | pytest + pytest-asyncio + pytest-docker | Async support + container orchestration |
| **Validation** | Pydantic field validators | Early error detection |

---

## Open Questions Resolved

All "NEEDS CLARIFICATION" items from the Technical Context have been addressed:

1. ✅ **SQLModel + pgvector integration**: Use `Field(sa_column=Column(Vector(1536)))`
2. ✅ **Async driver configuration**: asyncpg with SQLAlchemy async engine
3. ✅ **OpenTelemetry instrumentation**: Custom decorators + OTLP exporter
4. ✅ **Vector index type**: HNSW for Phase 1
5. ✅ **Migration strategy**: Alembic with async support
6. ✅ **Environment configuration**: Pydantic Settings
7. ✅ **Docker infrastructure**: ankane/pgvector + Jaeger all-in-one
8. ✅ **Session lifecycle**: Auto-created on first message
9. ✅ **Test strategy**: pytest + pytest-asyncio + pytest-docker
10. ✅ **Embedding validation**: Pydantic field validators

**Status**: All research complete. Ready for Phase 1 (Design & Contracts).

