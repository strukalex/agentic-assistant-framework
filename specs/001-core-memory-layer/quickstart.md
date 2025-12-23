# Quickstart Guide: Core Foundation and Memory Layer

**Feature**: Core Foundation and Memory Layer  
**Date**: 2025-12-21  
**Audience**: Developers implementing agents or workflows that need memory/observability

## Overview

This quickstart guide will walk you through:

1. Setting up the development environment
2. Starting PostgreSQL + Jaeger with Docker Compose
3. Running database migrations
4. Using the MemoryManager API
5. Viewing traces in Jaeger UI
6. Running tests

**Time to complete**: ~15 minutes

---

## Prerequisites

Before you begin, ensure you have:

- **Docker** 20.10+ and **Docker Compose** 1.29+ installed
- **Python** 3.11+ installed
- **Git** for cloning the repository
- Basic familiarity with async/await in Python

---

## Step 1: Clone and Install Dependencies

```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd agentic-assistant-framework

# Create and activate virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import sqlmodel, asyncpg, opentelemetry; print('✓ Dependencies installed')"
```

---

## Step 2: Start Infrastructure with Docker Compose

```bash
# Start PostgreSQL + Jaeger containers
docker-compose up -d

# Verify containers are running
docker-compose ps

# Expected output:
# NAME                COMMAND                  SERVICE             STATUS
# postgres            "docker-entrypoint.s…"   postgres            Up (healthy)
# jaeger              "/go/bin/all-in-one"     jaeger              Up (healthy)

# Check PostgreSQL logs (optional)
docker-compose logs -f postgres

# Check Jaeger logs (optional)
docker-compose logs -f jaeger
```

**Troubleshooting**:
- If port 5432 is already in use: Change `ports: - "5432:5432"` to `- "5433:5432"` in `docker-compose.yml` and update `DATABASE_URL` in `.env`
- If port 16686 is already in use: Change Jaeger UI port similarly

---

## Step 3: Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env file with your preferred editor
nano .env  # or vim, code, etc.
```

**Required environment variables** (`.env` file):

```bash
# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/paias
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10

# OpenTelemetry Configuration
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=paias-memory-layer
OTEL_SAMPLING_RATE=1.0

# Vector Search Configuration (configurable; default for OpenAI Ada-002)
VECTOR_DIMENSION=1536
HNSW_EF_SEARCH=40
```

**Note**: Default values work for local development. No changes needed if using standard Docker Compose setup.

---

## Step 4: Run Database Migrations

```bash
# Initialize Alembic (first time only)
alembic upgrade head

# Expected output:
# INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
# INFO  [alembic.runtime.migration] Will assume transactional DDL.
# INFO  [alembic.runtime.migration] Running upgrade  -> 001, Initial schema with pgvector

# Verify tables were created
docker exec -it postgres psql -U postgres -d paias -c "\dt"

# Expected output:
#           List of relations
# Schema |   Name    | Type  |  Owner
# --------+-----------+-------+----------
# public | sessions  | table | postgres
# public | messages  | table | postgres
# public | documents | table | postgres
```

**Troubleshooting**:
- If migration fails with "relation already exists": Run `alembic downgrade base` then `alembic upgrade head`
- If pgvector extension error: Verify you're using `ankane/pgvector` Docker image

---

## Step 5: Test MemoryManager API

Create a test script `test_memory.py`:

```python
import asyncio
from uuid import uuid4
from datetime import datetime
from core.memory import MemoryManager

async def test_memory():
    """Test basic MemoryManager operations."""
    memory = MemoryManager()
    
    # 1. Health check
    print("1. Checking database health...")
    health = await memory.health_check()
    print(f"   ✓ Status: {health['status']}")
    print(f"   ✓ PostgreSQL: {health['postgres_version']}")
    
    # 2. Store and retrieve messages
    print("\n2. Testing conversation storage...")
    session_id = uuid4()
    
    msg_id_1 = await memory.store_message(
        session_id=session_id,
        role="user",
        content="What is async programming?",
        metadata={"source": "test"}
    )
    print(f"   ✓ Stored user message: {msg_id_1}")
    
    msg_id_2 = await memory.store_message(
        session_id=session_id,
        role="assistant",
        content="Async programming enables non-blocking I/O operations.",
        metadata={"model": "deepseek-3.2", "confidence": 0.95}
    )
    print(f"   ✓ Stored assistant message: {msg_id_2}")
    
    # Retrieve history
    history = await memory.get_conversation_history(session_id, limit=10)
    print(f"   ✓ Retrieved {len(history)} messages")
    for msg in history:
        print(f"     - {msg.role}: {msg.content[:50]}...")
    
    # 3. Store document with embedding
    print("\n3. Testing document storage...")
    # Dummy embedding (1536 dimensions of random values)
    dummy_embedding = [0.1] * 1536
    
    doc_id = await memory.store_document(
        content="Async programming allows concurrent execution without threads.",
        metadata={"category": "programming", "topic": "async"},
        embedding=dummy_embedding
    )
    print(f"   ✓ Stored document: {doc_id}")
    
    # 4. Semantic search (using same embedding for demo)
    print("\n4. Testing semantic search...")
    results = await memory.semantic_search(
        query_embedding=dummy_embedding,
        top_k=5
    )
    print(f"   ✓ Found {len(results)} similar documents")
    for i, doc in enumerate(results, 1):
        print(f"     {i}. {doc.content[:50]}...")
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_memory())
```

Run the test:

```bash
python test_memory.py

# Expected output:
# 1. Checking database health...
#    ✓ Status: healthy
#    ✓ PostgreSQL: 15.3
#
# 2. Testing conversation storage...
#    ✓ Stored user message: <uuid>
#    ✓ Stored assistant message: <uuid>
#    ✓ Retrieved 2 messages
#      - user: What is async programming?...
#      - assistant: Async programming enables non-blocking I/O...
#
# 3. Testing document storage...
#    ✓ Stored document: <uuid>
#
# 4. Testing semantic search...
#    ✓ Found 1 similar documents
#      1. Async programming allows concurrent execution...
#
# ✅ All tests passed!
```

---

## Step 6: View Traces in Jaeger UI

1. Open your browser and navigate to: **http://localhost:16686**

2. In the Jaeger UI:
   - **Service**: Select `paias-memory-layer` from the dropdown
   - **Operation**: You should see operations like:
     - `memory.health_check`
     - `memory.store_message`
     - `memory.store_document`
     - `memory.semantic_search`
   - Click **Find Traces** to view trace history

3. Click on any trace to see:
   - **Duration**: How long the operation took
   - **Span details**: Attributes like `session_id`, `role`, `content_length`
   - **Error status**: Red spans indicate failures

**Example Trace Attributes**:

For `memory.store_message`:
```
operation.type: store_message
operation.success: true
session_id: <uuid>
role: user
content_length: 27
has_metadata: true
db.system: postgresql
```

---

## Step 7: Run Tests

```bash
# Run all tests with coverage
pytest --cov=src --cov-report=html tests/

# Expected output:
# ==================== test session starts ====================
# collected 25 items
#
# tests/unit/test_memory.py ................              [ 64%]
# tests/unit/test_telemetry.py .....                      [ 84%]
# tests/integration/test_database.py ....                 [100%]
#
# ==================== 25 passed in 5.32s ====================
#
# Coverage Report:
# Name                       Stmts   Miss  Cover
# ----------------------------------------------
# src/core/memory.py           150      5    97%
# src/core/telemetry.py         45      2    96%
# src/models/common.py          60      0   100%
# ----------------------------------------------
# TOTAL                        255      7    97%

# Open HTML coverage report
open htmlcov/index.html  # On macOS
# xdg-open htmlcov/index.html  # On Linux
# start htmlcov/index.html  # On Windows
```

**Running Specific Tests**:

```bash
# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run a specific test file
pytest tests/unit/test_memory.py

# Run a specific test function
pytest tests/unit/test_memory.py::test_store_message
```

---

## Step 8: Using MemoryManager in Your Code

### Example: Agent with Memory

```python
from uuid import uuid4
from core.memory import MemoryManager
from models.common import AgentResponse

class SimpleAgent:
    def __init__(self):
        self.memory = MemoryManager()
    
    async def process_message(self, session_id: uuid4, user_message: str) -> AgentResponse:
        """Process a user message with conversation context."""
        
        # 1. Store user message
        await self.memory.store_message(
            session_id=session_id,
            role="user",
            content=user_message
        )
        
        # 2. Retrieve conversation history
        history = await self.memory.get_conversation_history(session_id, limit=10)
        
        # 3. Generate response (simplified; real agent would use LLM)
        response_text = f"I understand you asked: {user_message}"
        
        # 4. Store assistant response
        await self.memory.store_message(
            session_id=session_id,
            role="assistant",
            content=response_text,
            metadata={"confidence": 0.9}
        )
        
        # 5. Return structured response
        return AgentResponse(
            answer=response_text,
            reasoning="Simple echo response",
            tool_calls=[],
            confidence=0.9
        )
```

### Example: RAG Pattern with Semantic Search

```python
from core.memory import MemoryManager

class RAGAgent:
    def __init__(self):
        self.memory = MemoryManager()
    
    async def answer_question(self, question: str, query_embedding: list[float]) -> str:
        """Answer a question using RAG (Retrieval Augmented Generation)."""
        
        # 1. Semantic search for relevant documents
        relevant_docs = await self.memory.semantic_search(
            query_embedding=query_embedding,
            top_k=3
        )
        
        # 2. Build context from retrieved documents
        context = "\n\n".join([doc.content for doc in relevant_docs])
        
        # 3. Generate answer using LLM (simplified)
        answer = f"Based on relevant documents:\n{context}\n\nAnswer: {question}"
        
        return answer
```

---

## Common Operations

### Creating a New Session

```python
# Implicit session creation (recommended)
session_id = uuid4()
await memory.store_message(session_id, "user", "Hello")
# Session is auto-created when first message is stored

# Explicit session creation (optional)
session_id = await memory.create_session(
    user_id="test_user",
    metadata={"session_type": "research"}
)
```

### Querying Documents by Date Range

```python
from datetime import datetime, timedelta

end_date = datetime.utcnow()
start_date = end_date - timedelta(days=7)

recent_docs = await memory.temporal_query(
    start_date=start_date,
    end_date=end_date,
    metadata_filters={"category": "research"}
)
```

### Combining Semantic Search with Metadata Filters

```python
results = await memory.semantic_search(
    query_embedding=embedding,
    top_k=10,
    metadata_filters={"source": "arxiv", "year": "2024"}
)
```

---

## Troubleshooting

### Database Connection Errors

**Error**: `asyncpg.exceptions.ConnectionDoesNotExistError`

**Solution**:
```bash
# 1. Verify PostgreSQL is running
docker-compose ps

# 2. Check database logs
docker-compose logs postgres

# 3. Test connection manually
docker exec -it postgres psql -U postgres -d paias -c "SELECT 1;"
```

### Migration Errors

**Error**: `alembic.util.exc.CommandError: Can't locate revision identified by 'xxx'`

**Solution**:
```bash
# Reset migration state
alembic downgrade base
alembic upgrade head
```

### Jaeger Traces Not Appearing

**Checklist**:
1. Verify Jaeger is running: `docker-compose ps jaeger`
2. Check Jaeger UI is accessible: http://localhost:16686
3. Verify OTLP endpoint: `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` in `.env`
4. Check sampling rate: `OTEL_SAMPLING_RATE=1.0` (100% sampling)

### Test Failures

**Error**: `pytest: command not found`

**Solution**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall test dependencies
pip install pytest pytest-asyncio pytest-cov pytest-docker
```

---

## Next Steps

Now that you have the Core Foundation and Memory Layer running, you can:

1. **Build Agents**: Create Pydantic AI agents that use MemoryManager for conversation history
2. **Implement RAG**: Use semantic search for retrieval-augmented generation
3. **Add Workflows**: Integrate memory layer with Windmill workflows
4. **Monitor Performance**: Use Jaeger to identify slow database queries
5. **Extend Models**: Add custom Pydantic models in `models/common.py`

---

## Useful Commands

### Docker Compose

```bash
# Start services
docker-compose up -d

# Stop services (keep data)
docker-compose stop

# Stop and remove containers + volumes (delete data)
docker-compose down -v

# View logs
docker-compose logs -f [postgres|jaeger]

# Restart a service
docker-compose restart postgres
```

### Database

```bash
# Connect to PostgreSQL
docker exec -it postgres psql -U postgres -d paias

# List tables
\dt

# Describe table schema
\d sessions

# Query data
SELECT * FROM sessions LIMIT 10;

# Exit psql
\q
```

### Alembic

```bash
# Show current migration version
alembic current

# Show migration history
alembic history

# Upgrade to latest version
alembic upgrade head

# Downgrade one version
alembic downgrade -1

# Create new migration (for future changes)
alembic revision --autogenerate -m "Description"
```

---

## Additional Resources

- **API Contract**: See `specs/001-core-memory-layer/contracts/README.md` for complete API reference
- **Data Model**: See `specs/001-core-memory-layer/data-model.md` for schema details
- **Research Decisions**: See `specs/001-core-memory-layer/research.md` for technical rationale
- **Constitution**: See `.specify/memory/constitution.md` for architectural principles

---

## Getting Help

If you encounter issues:

1. **Check logs**: `docker-compose logs postgres` and `docker-compose logs jaeger`
2. **Verify environment**: Ensure `.env` file has correct DATABASE_URL
3. **Run health check**: `python -c "import asyncio; from core.memory import MemoryManager; asyncio.run(MemoryManager().health_check())"`
4. **Review tests**: Unit tests in `tests/unit/` demonstrate correct usage patterns

---

## Summary

You've successfully:

- ✅ Set up PostgreSQL + Jaeger with Docker Compose
- ✅ Ran database migrations with Alembic
- ✅ Used MemoryManager API for conversation storage and semantic search
- ✅ Viewed traces in Jaeger UI
- ✅ Ran tests with 80%+ coverage

**Next milestone**: Build your first Pydantic AI agent that uses the MemoryManager!

