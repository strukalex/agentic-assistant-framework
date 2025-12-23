# Feature Specification: Core Foundation and Memory Layer

**Feature Branch**: `001-core-memory-layer`  
**Created**: 2025-12-21  
**Status**: Draft  
**Input**: User description: "Build the Core Foundation and Memory Layer for the PAIAS Phase 1 Vertical Slice."

## Constitution Constraints *(mandatory)*

**Source of truth**: `.specify/memory/constitution.md` (v2.0+)  
**Project context**: `.specify/memory/project-context.md` (current phase, decisions, open questions)

This feature MUST comply with the constitution's non-negotiables. If a requirement
conflicts with any item below, it MUST be escalated via **Article V (Amendment Process)**.

- **Technology stack (Article I)**:
  - **Python 3.11+**
  - **Orchestration**: Pattern-driven selection (Article I.B)—Windmill for DAG/linear workflows, LangGraph for cyclical reasoning, CrewAI for role-based teams, AutoGen for agent negotiation
  - **Agents**: Pydantic AI (atomic agent unit)
  - **Memory**: PostgreSQL 15+ + pgvector (PostgreSQL is source of truth; memory abstraction layer required)
  - **Tools**: MCP-only integrations (no hardcoded tool clients)
  - **UI**: Streamlit for Phase 1-2 (proof-of-concept); React/Next.js OR LibreChat for Phase 3+ (decision pending Phase 2 evaluation) *(Article I.F)*
- **Default model**: DeepSeek 3.2 via Microsoft Azure AI Foundry (model-agnostic agents via Pydantic AI)
- **Architectural principles (Article II)**: All 7 principles apply (vertical-slice, pluggable orchestration, human-in-the-loop, observable everything, multi-storage abstraction, isolation & safety boundaries, tool gap detection).
- **Quality gates (Article III)**: Testing is required; CI enforces **≥ 80% coverage**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Store and Retrieve Conversation Context (Priority: P1)

As a system developer building agents, I need the ability to store chat messages and retrieve them by session, so agents can maintain context across multiple interactions with users.

**Why this priority**: This is the foundational capability for any conversational agent system. Without persistent conversation history, agents cannot provide contextual responses or remember past interactions.

**Independent Test**: Can be fully tested by storing messages via the memory API, retrieving them by session ID, and verifying the correct messages are returned in chronological order. Delivers immediate value for any agent that needs conversation context.

**Acceptance Scenarios**:

1. **Given** a new user session, **When** agent stores a user message followed by an assistant response, **Then** both messages are persisted with correct role, content, timestamp, and session ID
2. **Given** a session with 50 historical messages, **When** retrieving conversation history with limit=10, **Then** the most recent 10 messages are returned in chronological order
3. **Given** multiple concurrent sessions, **When** retrieving history for session A, **Then** only messages from session A are returned (no cross-session leakage)

---

### User Story 2 - Store and Search Documents Semantically (Priority: P1)

As an agent developer, I need to store documents with vector embeddings and search them by semantic similarity, so agents can retrieve relevant information from a knowledge base using natural language queries.

**Why this priority**: Semantic search is the core capability that enables RAG (Retrieval Augmented Generation) patterns. This is essential for the Phase 1 ResearcherAgent to find relevant documents and answer questions accurately.

**Independent Test**: Can be fully tested by storing documents with embeddings, performing semantic searches with natural language queries, and verifying relevant documents are returned in order of similarity. Delivers immediate value for knowledge retrieval tasks.

**Acceptance Scenarios**:

1. **Given** 100 documents stored with vector embeddings, **When** querying with "What are the benefits of async programming?", **Then** documents discussing async/await, concurrency, and performance are returned ranked by relevance
2. **Given** documents stored with metadata tags (category, source, date), **When** performing semantic search with metadata filters, **Then** only documents matching both semantic similarity and metadata criteria are returned
3. **Given** a semantic search query, **When** no documents have similarity above threshold, **Then** an empty result set is returned (not an error)

---

### User Story 3 - Query Documents by Time and Metadata (Priority: P2)

As an agent developer, I need to filter documents by date ranges and structured metadata, so agents can retrieve temporally-relevant information or documents from specific sources.

**Why this priority**: Temporal and metadata filtering enables more sophisticated retrieval patterns (e.g., "find research papers from last quarter" or "show documentation from version 2.x"). This complements semantic search for complex queries.

**Independent Test**: Can be fully tested by storing documents with timestamps and metadata, querying by date ranges or metadata filters, and verifying the correct subset is returned. Delivers value for time-sensitive or source-specific retrieval.

**Acceptance Scenarios**:

1. **Given** documents spanning 6 months, **When** querying for documents from the last 30 days, **Then** only documents created or modified within that range are returned
2. **Given** documents with metadata {"category": "research", "source": "arxiv"}, **When** filtering by category="research", **Then** all research documents are returned regardless of source
3. **Given** a combined query (date range + metadata + semantic search), **When** executing the query, **Then** results satisfy all three criteria (AND logic)

---

### User Story 4 - Observe All Database Operations (Priority: P2)

As a system operator, I need all database operations to emit OpenTelemetry trace spans, so I can monitor performance, debug issues, and understand query patterns in production.

**Why this priority**: Observability is a constitutional requirement (Article II.D) and critical for operating the system in production. This enables troubleshooting slow queries, identifying bottlenecks, and understanding agent behavior.

**Independent Test**: Can be fully tested by performing memory operations (store, search, query) and verifying that corresponding trace spans appear in Jaeger with correct attributes (operation name, duration, parameters). Delivers immediate value for debugging and performance monitoring.

**Acceptance Scenarios**:

1. **Given** Jaeger is running, **When** storing a document via MemoryManager, **Then** a trace span named "memory.store_document" appears in Jaeger with document ID and metadata attributes
2. **Given** a semantic search operation, **When** the search completes, **Then** Jaeger shows a trace with query text, top_k parameter, number of results, and query duration
3. **Given** a database error (e.g., connection timeout), **When** the operation fails, **Then** the trace span is marked as error with exception details

---

### User Story 5 - Run Database Migrations Safely (Priority: P3)

As a DevOps engineer, I need repeatable database migrations that can be applied forward and rolled back, so schema changes can be deployed safely across environments without manual SQL execution.

**Why this priority**: Migration management is important for long-term maintainability but not required for the first vertical slice. The initial schema can be bootstrapped directly for Phase 1 demos.

**Independent Test**: Can be fully tested by running `alembic upgrade head` on a fresh database, verifying schema creation, then running `alembic downgrade -1` and confirming rollback. Delivers value for safe schema evolution.

**Acceptance Scenarios**:

1. **Given** a fresh PostgreSQL database, **When** running `alembic upgrade head`, **Then** all tables (sessions, messages, documents) are created with correct schema and pgvector extension is enabled
2. **Given** a database at migration version N, **When** running `alembic downgrade N-1`, **Then** the most recent migration is rolled back and schema returns to previous state
3. **Given** a migration failure midway, **When** the migration is retried, **Then** the migration system detects partial state and either completes or provides clear error message

---

### Edge Cases

- **What happens when storing a document without embeddings?** System should either reject the document with a validation error OR store it with null vector field (based on whether embeddings are mandatory or optional)
- **What happens when semantic search is called with an empty query string?** System returns validation error indicating query cannot be empty
- **What happens when database connection is lost mid-operation?** System raises a connection error that can be caught and retried by the calling code; trace span is marked as error
- **What happens when storing a message with session_id that doesn't exist in sessions table?** System either auto-creates the session OR enforces foreign key constraint (requires clarification on session lifecycle management)
- **What happens when vector dimension mismatch occurs?** (e.g., storing 768-dim embedding in 1536-dim column) PostgreSQL raises dimension error; system should validate dimension before insertion
- **What happens when querying with top_k=0 or negative value?** System validates input and raises ValueError before executing query

## Requirements *(mandatory)*

### Functional Requirements

#### Memory Storage

- **FR-001**: System MUST provide an abstraction layer for all memory operations that prevents agents from directly importing database drivers (SQLAlchemy, asyncpg, psycopg2)
- **FR-002**: System MUST store conversation messages with the following attributes: session_id (UUID), role (user/assistant/system), content (text), timestamp (UTC), and optional metadata (JSONB)
- **FR-003**: System MUST store documents with the following attributes: document_id (UUID), content (text), vector_embedding (1536-dimensional float array), metadata (JSONB), and created_at/updated_at timestamps
- **FR-004**: System MUST store user sessions with attributes: session_id (UUID), user_id (string), created_at/updated_at timestamps, and optional session metadata (JSONB)
- **FR-005**: System MUST use async/await patterns for all database operations to support non-blocking I/O

#### Memory Retrieval

- **FR-006**: System MUST provide semantic_search(query, top_k) that returns the top K most similar documents using cosine similarity on vector embeddings
- **FR-007**: System MUST provide get_conversation_history(session_id, limit) that returns the most recent N messages for a session in chronological order
- **FR-008**: System MUST provide temporal_query(date_range, filters) that returns documents matching date range and optional metadata filters
- **FR-009**: System MUST return all query results as Pydantic models (not raw database rows or dictionaries)
- **FR-010**: System MUST handle empty result sets gracefully (return empty list, not raise exception)

#### Data Integrity

- **FR-011**: System MUST create database indexes on: session_id (for message queries), vector embeddings (for similarity search using pgvector IVFFlat or HNSW), and JSONB metadata fields (GIN index)
- **FR-012**: System MUST validate all input data using Pydantic models before database operations
- **FR-013**: System MUST use UUID v4 for all primary keys (sessions, messages, documents)
- **FR-014**: System MUST store all timestamps in UTC timezone
- **FR-015**: System MUST enforce NOT NULL constraints on critical fields (session_id, role, content, timestamps)

#### Observability

- **FR-016**: System MUST emit OpenTelemetry trace spans for every database operation (insert, select, update, delete)
- **FR-017**: System MUST include operation-specific attributes in trace spans: operation type, table name, number of rows affected, query parameters (excluding sensitive data)
- **FR-018**: System MUST export traces to Jaeger using OTLP exporter
- **FR-019**: System MUST use 100% sampling rate for Phase 1 (all operations traced)
- **FR-020**: System MUST tag trace spans with service.name="paias-memory-layer"

#### Infrastructure

- **FR-021**: System MUST provide docker-compose.yml that starts PostgreSQL 15+ with pgvector extension pre-installed
- **FR-022**: System MUST provide docker-compose.yml that starts Jaeger all-in-one container with UI accessible on port 16686
- **FR-023**: System MUST use environment variables for all configuration (database connection strings, Jaeger endpoints)
- **FR-024**: System MUST initialize pgvector extension automatically during first database connection or via migration
- **FR-025**: System MUST provide health check endpoints/functions to verify database and Jaeger connectivity

#### Database Migrations

- **FR-026**: System MUST use Alembic for database schema migrations
- **FR-027**: System MUST provide initial migration that creates all three tables (sessions, messages, documents)
- **FR-028**: System MUST support both upgrade (forward) and downgrade (rollback) operations for all migrations
- **FR-029**: System MUST include pgvector extension setup in the initial migration
- **FR-030**: System MUST version migrations with timestamp and descriptive names

### Key Entities

- **Session**: Represents a user interaction session. Attributes include unique session identifier, user identifier, creation timestamp, last activity timestamp, and optional metadata (e.g., session type, tags, configuration). Sessions are the top-level container for conversation threads.

- **Message**: Represents a single message in a conversation. Attributes include unique message identifier, parent session reference, role (user/assistant/system), message content, timestamp, and optional metadata (e.g., token count, model used, confidence score). Messages are always associated with exactly one session.

- **Document**: Represents a piece of stored knowledge with semantic search capability. Attributes include unique document identifier, textual content, vector embedding (1536 dimensions for OpenAI Ada-002 compatibility), structured metadata (source, category, tags, author), creation timestamp, and last updated timestamp. Documents exist independently of sessions but can be referenced in message metadata.

- **Vector Embedding**: A high-dimensional numerical representation of document content (1536 float values) used for semantic similarity calculations. Stored using PostgreSQL pgvector extension with support for cosine distance queries.

- **Metadata**: Flexible JSONB structure attached to sessions, messages, and documents. Enables filtering and tagging without schema changes. Common fields include: source (origin of data), category (classification), tags (array of labels), version (for documents), confidence (for model outputs).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Developers can store and retrieve conversation messages in under 100ms for sessions with up to 1000 messages
- **SC-002**: Semantic search returns relevant results (top-10) in under 500ms for document collections up to 10,000 items
- **SC-003**: All database operations emit trace spans visible in Jaeger UI within 5 seconds of execution
- **SC-004**: The system starts successfully with `docker-compose up` on a fresh machine with only Docker installed (no manual database setup required)
- **SC-005**: Database schema can be created and destroyed repeatably via migration commands without data loss or corruption
- **SC-006**: Developers can import and use MemoryManager without any knowledge of underlying database technology (complete abstraction)
- **SC-007**: The memory layer maintains 99.9% uptime during Phase 1 testing (minimal crashes or connection failures)
- **SC-008**: Vector similarity search returns semantically relevant documents in the top 3 results for 90% of test queries
- **SC-009**: All Pydantic models validate successfully with 100% coverage of required and optional fields
- **SC-010**: System handles concurrent operations from 10 simultaneous sessions without deadlocks or race conditions

## Assumptions

- **Embedding generation**: This specification assumes embeddings are generated externally (by agents or a separate service) and passed to MemoryManager.store_document(). The memory layer is responsible for storage and retrieval only, not embedding generation.
- **Authentication**: Phase 1 does not include user authentication. The user_id field in sessions is a string identifier assumed to be provided by the calling code (could be "test_user" or a mock ID).
- **Session lifecycle**: Sessions are created implicitly when the first message is stored. Explicit session creation/deletion APIs are not required for Phase 1 but may be added in future phases.
- **Embedding model compatibility**: The 1536-dimensional embedding size is chosen for OpenAI Ada-002 compatibility. If other embedding models are used, they should either match this dimension or the schema should be updated.
- **Connection pooling**: Database connection pooling is handled by SQLAlchemy/asyncpg defaults. Fine-tuning pool size is deferred to Phase 2 performance optimization.
- **Data retention**: No automatic data deletion or archival is implemented in Phase 1. All data persists indefinitely. Retention policies are planned for Phase 2.
- **PII handling**: Phase 1 stores all content as plaintext. PII encryption (Article III.B requirement) will be implemented in Phase 2 when multi-user deployment begins.
- **Vector index type**: The specification assumes pgvector HNSW or IVFFlat index. The specific index type and parameters (e.g., m, ef_construction for HNSW) can be tuned during implementation based on dataset size and query performance.
- **Jaeger deployment**: Phase 1 uses Jaeger all-in-one container (in-memory storage). Production-grade Jaeger with persistent storage is planned for Phase 3.
- **Error handling**: Database errors (connection failures, constraint violations) are raised as exceptions to the calling code. Automatic retry logic is not implemented in the memory layer but may be added at the orchestration level.

## Dependencies

- **PostgreSQL 15+ with pgvector extension**: Must be available via Docker or system installation
- **Python packages**: SQLModel, asyncpg, pydantic, opentelemetry-sdk, opentelemetry-exporter-otlp, alembic
- **Docker and Docker Compose**: Required for local development and testing
- **Jaeger**: Required for trace collection and visualization
- **No dependencies on**: Specific agent implementations, orchestration frameworks, or UI components (memory layer is completely independent)

## Out of Scope (Future Phases)

- **Multi-tenant isolation**: Phase 1 assumes single-user or development environment. True multi-tenancy with data isolation between users is planned for Phase 3.
- **PII encryption at rest**: Plaintext storage is acceptable for Phase 1. Encryption for sensitive fields will be added in Phase 2.
- **Distributed tracing across services**: Phase 1 traces only the memory layer. Full distributed tracing across agents, orchestration, and UI is planned for Phase 2.
- **Advanced vector index optimization**: Phase 1 uses default pgvector indexes. Performance tuning (index types, parameters, quantization) is deferred to Phase 2.
- **Real-time synchronization**: No support for real-time updates or pub/sub patterns in Phase 1. If needed, this can be added via PostgreSQL LISTEN/NOTIFY in Phase 2.
- **Data export/import tools**: No bulk data migration tools in Phase 1. Can be added in Phase 2 if needed.
- **Memory layer clustering/replication**: Phase 1 uses a single PostgreSQL instance. High availability and read replicas are planned for Phase 3.
- **Automatic embedding generation**: The memory layer does not generate embeddings. This responsibility belongs to agents or a separate embedding service.
- **Vector dimension flexibility**: Phase 1 hardcodes 1536 dimensions. Support for multiple embedding models with different dimensions can be added in Phase 2.

