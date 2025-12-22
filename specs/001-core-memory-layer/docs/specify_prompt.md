```

/speckit.specify Build the Core Foundation and Memory Layer for the PAIAS Phase 1 Vertical Slice.

This layer includes:

1. PostgreSQL Database Schema with pgvector Extension
   - Tables: sessions (user interactions), messages (chat history), documents (with vector embeddings)
   - Use pgvector extension for 1536-dimensional embeddings (OpenAI compatible)
   - Include proper indexes for JSONB metadata and vector similarity search

2. MemoryManager Abstraction Class
   - Create core/memory.py with async methods:
     - store_document(content, metadata) -> UUID
     - semantic_search(query, top_k) -> List[Document]
     - store_message(session_id, role, content) -> UUID
     - get_conversation_history(session_id, limit) -> List[Message]
     - temporal_query(date_range, filters) -> List[Document]
   - Use asyncpg + SQLAlchemy 2.0 async
   - This abstraction ensures agents never import database drivers directly (Constitution Article II.E)

3. Base Pydantic Models (models/common.py)
   - AgentResponse: answer, reasoning, tool_calls, confidence, timestamp
   - ToolGapReport: missing_tools, attempted_task, existing_tools_checked, proposed_mcp_server
   - ApprovalRequest: action_type, action_description, confidence, tool_name, parameters, requires_immediate_approval
   - RiskLevel: Enum (reversible, reversible_with_delay, irreversible)

4. OpenTelemetry Configuration
   - Initialize OpenTelemetry SDK with Jaeger exporter (local deployment)
   - Create core/telemetry.py with decorators: @trace_agent_execution, @trace_tool_call, @trace_memory_operation
   - Configure 100% sampling for Phase 1
   - Add Jaeger service to docker-compose.yml (port 16686)

5. Docker Compose Infrastructure
   - PostgreSQL 15 with pgvector extension pre-installed
   - Jaeger all-in-one for trace collection
   - Environment variables for connection strings

6. Database Migrations with Alembic
   - Initial migration for all three tables
   - Include pgvector extension setup
   - Test rollback capability

Constraints (from Constitution v2.0):
- Python 3.11+ with asyncio (Article I.A)
- SQLModel (built on SQLAlchemy 2.0) with asyncpg driver
- Use SQLModel for unified Pydantic/ORM models (single source of truth)
- For pgvector columns, use: Field(sa_column=Column(Vector(1536)))
- 80%+ test coverage with pytest (Article III.A)
- Strict mypy type checking on all Pydantic models
- All database operations must generate OpenTelemetry trace spans (Article II.D)

Success Criteria:
- docker-compose up starts PostgreSQL + Jaeger successfully
- Can insert and query vector embeddings via MemoryManager
- MemoryManager.semantic_search() returns relevant documents
- All Pydantic models validate correctly
- Jaeger UI (localhost:16686) shows trace spans for database operations

```