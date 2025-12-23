# 🧠 Personal AI Assistant System (PAIAS)

Core foundation and memory layer for the PAIAS vertical slice. Built with Python 3.11, SQLModel, asyncpg, pgvector, and OpenTelemetry, and shipped with Docker Compose for PostgreSQL + Jaeger.

## What's Included

- Async `MemoryManager` with conversation history, document storage, semantic search, temporal queries, and health checks.
- SQLModel models with pgvector columns, Alembic migrations, and JSONB metadata support.
- OpenTelemetry tracing for every database operation (Jaeger-ready).
- Comprehensive tests (unit + integration) with an 80% coverage gate.

## Prerequisites

- Python 3.11+
- Docker + Docker Compose (for PostgreSQL 15 + pgvector + Jaeger)
- Git

## Setup

```bash
git clone <repository-url>
cd agentic-assistant-framework

# Virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install with dev tools
pip install -e .[dev]

# Environment variables
cp .env.example .env
```

## Run the stack

```bash
# Start PostgreSQL + Jaeger
docker-compose up -d

# Apply migrations
alembic upgrade head
```

## Quality Gates

```bash
# Format
black src tests

# Lint
ruff check src tests

# Type-check
mypy src

# Tests + coverage (>=80%)
pytest --cov=src --cov-fail-under=80
```

## Using MemoryManager

```python
import asyncio
from uuid import uuid4
from core.memory import MemoryManager

async def demo():
    memory = MemoryManager()
    session_id = uuid4()
    await memory.store_message(session_id, role="user", content="Hello!")
    await memory.store_document(
        content="Async programming enables non-blocking I/O.",
        embedding=[0.1] * 1536,
        metadata={"topic": "async"},
    )
    history = await memory.get_conversation_history(session_id, limit=10)
    results = await memory.semantic_search(query_embedding=[0.1] * 1536, top_k=5)
    print(len(history), len(results))

asyncio.run(demo())
```

## Project Structure

```
src/
  core/          # config, telemetry, memory manager
  models/        # SQLModel + Pydantic models
tests/
  unit/          # validation + telemetry tests
  integration/   # database + semantic search + migrations
  fixtures/      # sample documents and shared fixtures
alembic/
  versions/      # migration scripts
docker-compose.yml  # PostgreSQL + Jaeger for local dev
```

## Observability

- Tracing exporter: OTLP gRPC → Jaeger (`OTEL_EXPORTER_OTLP_ENDPOINT`)
- Service name: `paias-memory-layer`
- 100% sampling in development (`OTEL_SAMPLING_RATE=1.0`)

## Troubleshooting

- Postgres not reachable: check `docker-compose ps` and `DATABASE_URL` in `.env`.
- pgvector issues: ensure the `ankane/pgvector` image is running; rerun `alembic upgrade head`.
- Traces missing: verify Jaeger on `http://localhost:16686` and OTLP endpoint in `.env`.

## Further Reading

- `specs/001-core-memory-layer/quickstart.md`
- `specs/001-core-memory-layer/contracts/README.md`
- `specs/001-core-memory-layer/data-model.md`
