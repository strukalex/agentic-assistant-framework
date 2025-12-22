# Tasks: Core Foundation and Memory Layer

**Input**: Design documents from `/specs/001-core-memory-layer/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are **REQUIRED** to meet the project constitution's quality gate (**≥ 80% coverage**).
Any exception MUST be explicitly justified and approved via **Article V (Amendment Process)** in
`.specify/memory/constitution.md`.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4, US5)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Paths shown below follow the structure from plan.md

## Constitution-driven cross-cutting requirements *(mandatory)*

**Source of truth**: `.specify/memory/constitution.md` (v2.1)  
**Project context**: `.specify/memory/project-context.md` (current phase, workflow guidelines, blockers)

Include tasks to satisfy these non-negotiables (refer to the cited Articles in task descriptions):

- **Article I — Technology stack**: Python 3.11+, SQLModel 0.0.14+, asyncpg 0.30+, Pydantic 2.0+, opentelemetry-sdk 1.20+, alembic 1.13+ (Article I.A, I.D, I.H)
- **Article II — Architectural principles (all 7)**:
  - Observable everything (OpenTelemetry traces for all database operations - Article II.D)
  - Multi-storage memory abstraction (no direct DB driver imports in agent code - Article II.E)
  - Isolation & safety boundaries (async-compatible, Docker containerized - Article II.F)
- **Article III — Operational standards**:
  - Async I/O for all database operations (Article III.B)
  - Alembic migrations for schema changes (Article III.D)
  - CI gates for lint/type-check/tests and **coverage ≥ 80%** (Article III.A)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and Docker infrastructure

 - [X] T001 Create Python project structure with src/, tests/, alembic/ directories per plan.md
 - [X] T002 Create pyproject.toml with dependencies: SQLModel 0.0.14+, asyncpg 0.30+, Pydantic 2.0+, opentelemetry-sdk 1.20+, opentelemetry-exporter-otlp 1.20+, alembic 1.13+, pytest 7.0+, pytest-asyncio 0.21+, pytest-cov 4.0+
 - [X] T003 [P] Create docker-compose.yml with PostgreSQL 15 (ankane/pgvector image) and Jaeger all-in-one services per FR-021, FR-022
 - [X] T004 [P] Create .env.example with DATABASE_URL, OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SERVICE_NAME, VECTOR_DIMENSION, HNSW_EF_SEARCH per research.md section 6
 - [X] T005 [P] Create .gitignore with Python, .env, __pycache__, htmlcov/, .pytest_cache/ entries
 - [X] T006 [P] Create README.md with project overview, setup instructions, quick start commands
 - [X] T007 [P] Configure pytest.ini with asyncio_mode = auto and coverage settings (--cov-fail-under=80) per Article III.A
 - [X] T008 [P] Configure pyproject.toml with Ruff + Black + mypy settings per constitution Article I.H

**Checkpoint**: Project structure and Docker infrastructure ready

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T009 Create src/core/__init__.py (empty module initialization)
- [X] T010 Create src/models/__init__.py (empty module initialization)
- [X] T011 Create tests/unit/__init__.py (empty module initialization)
- [X] T012 Create tests/integration/__init__.py (empty module initialization)
- [X] T013 Create tests/fixtures/__init__.py (empty module initialization)
- [X] T014 [P] Implement Pydantic Settings configuration in src/core/config.py per research.md section 6 with database_url, otel_endpoint, vector_dimension, hnsw_ef_search
- [X] T015 [P] Initialize OpenTelemetry SDK in src/core/telemetry.py with TracerProvider, OTLPSpanExporter, BatchSpanProcessor per research.md section 3
- [X] T016 [P] Create @trace_memory_operation decorator in src/core/telemetry.py with span attributes (operation.type, operation.success, db.system) per FR-016, FR-017
- [X] T017 [P] Create MessageRole enum in src/models/message.py with values (USER, ASSISTANT, SYSTEM) per data-model.md
- [X] T018 [P] Create RiskLevel enum in src/models/common.py with values (REVERSIBLE, REVERSIBLE_WITH_DELAY, IRREVERSIBLE) per data-model.md
- [X] T019 Initialize Alembic in alembic/ directory with alembic init per research.md section 5
- [X] T020 Configure alembic/env.py for async SQLAlchemy engine with asyncpg driver per research.md section 5
- [X] T021 Create tests/fixtures/conftest.py with pytest fixtures for async database session, Docker Compose service waits per research.md section 9

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Store and Retrieve Conversation Context (Priority: P1) 🎯 MVP

**Goal**: Enable agents to store chat messages and retrieve them by session for conversation context

**Independent Test**: Store messages via memory API, retrieve by session ID, verify correct messages returned in chronological order

### Tests for User Story 1 (REQUIRED) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T022 [P] [US1] Create unit test for Session model validation in tests/unit/test_models.py - test UUID generation, user_id validation, metadata_ JSONB field
- [X] T023 [P] [US1] Create unit test for Message model validation in tests/unit/test_models.py - test role enum, content not empty, foreign key to session
- [X] T024 [P] [US1] Create integration test for store_message in tests/integration/test_database.py - test message persistence with auto-session creation per research.md section 8
- [X] T025 [P] [US1] Create integration test for get_conversation_history in tests/integration/test_database.py - test retrieval limit, chronological order, session isolation per spec.md acceptance scenarios

### Implementation for User Story 1

- [X] T026 [P] [US1] Create Session SQLModel in src/models/session.py with fields (id UUID, user_id str, created_at datetime, updated_at datetime, metadata_ JSONB) per data-model.md table definition
- [X] T027 [P] [US1] Create Message SQLModel in src/models/message.py with fields (id UUID, session_id UUID FK, role MessageRole enum, content str, created_at datetime, metadata_ JSONB) per data-model.md table definition
- [X] T028 [US1] Initialize async database engine in src/core/memory.py using asyncpg with connection string from config per research.md section 2
- [X] T029 [US1] Create async session factory in src/core/memory.py with AsyncSession, expire_on_commit=False per research.md section 2
- [X] T030 [US1] Implement MemoryManager.store_message method in src/core/memory.py with auto-session creation, input validation, OpenTelemetry span per contracts/README.md and research.md section 8
- [X] T031 [US1] Implement MemoryManager.get_conversation_history method in src/core/memory.py with session_id filter, limit parameter, chronological ordering per contracts/README.md and FR-007
- [X] T032 [US1] Add Pydantic field validators for Message.content (non-empty) and Session.user_id (max 255 chars) per data-model.md validation rules
- [X] T033 [US1] Add OpenTelemetry span attributes to store_message (session_id, role, content_length, has_metadata) per FR-017
- [X] T034 [US1] Add OpenTelemetry span attributes to get_conversation_history (session_id, limit, result_count) per FR-017

**Checkpoint**: At this point, User Story 1 should be fully functional - agents can store and retrieve conversation history

---

## Phase 4: User Story 2 - Store and Search Documents Semantically (Priority: P1)

**Goal**: Enable agents to store documents with vector embeddings and perform semantic similarity search

**Independent Test**: Store documents with embeddings, perform semantic searches, verify relevant documents returned in similarity order

### Tests for User Story 2 (REQUIRED) ⚠️

- [ ] T035 [P] [US2] Create unit test for Document model validation in tests/unit/test_models.py - test UUID generation, embedding dimension validation (1536), metadata_ JSONB field
- [ ] T036 [P] [US2] Create unit test for embedding validation in tests/unit/test_models.py - test dimension mismatch error, non-numeric values error, null embedding allowed per data-model.md validation rules and research.md section 10
- [ ] T037 [P] [US2] Create integration test for store_document in tests/integration/test_database.py - test document persistence with and without embeddings per FR-003
- [ ] T038 [P] [US2] Create integration test for semantic_search in tests/integration/test_semantic_search.py - test cosine similarity ranking, top_k parameter, metadata filters, empty results per spec.md acceptance scenarios

### Implementation for User Story 2

- [ ] T039 [P] [US2] Create Document SQLModel in src/models/document.py with fields (id UUID, content str, embedding Vector(1536), metadata_ JSONB, created_at datetime, updated_at datetime) using Field(sa_column=Column(Vector(1536))) per data-model.md and research.md section 1
- [ ] T040 [US2] Implement MemoryManager.store_document method in src/core/memory.py with content validation, embedding validation (1536 dims), OpenTelemetry span per contracts/README.md and FR-003
- [ ] T041 [US2] Implement MemoryManager.semantic_search method in src/core/memory.py with cosine distance query, top_k parameter, metadata filters using JSONB where clause per contracts/README.md, FR-006, and research.md section 4
- [ ] T042 [US2] Add Pydantic field validator for Document.embedding in src/models/document.py - validate dimension=1536, all numeric values per data-model.md validation rules and research.md section 10
- [ ] T043 [US2] Add Pydantic field validator for Document.content in src/models/document.py - validate non-empty string per data-model.md validation rules
- [ ] T044 [US2] Add OpenTelemetry span attributes to store_document (content_length, has_embedding, metadata_keys) per FR-017
- [ ] T045 [US2] Add OpenTelemetry span attributes to semantic_search (top_k, filter_count, result_count, query_time_ms) per FR-017

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently - agents have conversation memory and semantic search

---

## Phase 5: User Story 4 - Observe All Database Operations (Priority: P2)

**Goal**: Emit OpenTelemetry trace spans for all database operations visible in Jaeger UI

**Independent Test**: Perform memory operations, verify trace spans appear in Jaeger with correct attributes

**Note**: This user story is implemented early (before US3) because observability is foundational and enhances debugging for all subsequent work

### Tests for User Story 4 (REQUIRED) ⚠️

- [ ] T046 [P] [US4] Create unit test for @trace_memory_operation decorator in tests/unit/test_telemetry.py - test span creation, attribute setting, error handling
- [ ] T047 [P] [US4] Create integration test for trace export in tests/integration/test_database.py - test that store_message, semantic_search emit spans visible to in-memory exporter (mock Jaeger)

### Implementation for User Story 4

- [ ] T048 [US4] Configure OpenTelemetry service.name resource attribute in src/core/telemetry.py with value "paias-memory-layer" per FR-020
- [ ] T049 [US4] Set OpenTelemetry sampling rate to 1.0 (100%) in src/core/telemetry.py per FR-019
- [ ] T050 [US4] Verify all MemoryManager methods (store_message, get_conversation_history, store_document, semantic_search) use @trace_memory_operation decorator
- [ ] T051 [US4] Add error span recording in @trace_memory_operation decorator - set span.set_attribute("operation.success", False) and span.record_exception(e) on database errors per contracts/README.md
- [ ] T052 [US4] Add db.statement attribute to trace spans (sanitized SQL query without sensitive data) per FR-017
- [ ] T053 [US4] Document trace span attributes in contracts/README.md OpenTelemetry section (already exists, verify implementation matches)

**Checkpoint**: All database operations now emit trace spans - operators can monitor performance and debug issues in Jaeger UI

---

## Phase 6: User Story 3 - Query Documents by Time and Metadata (Priority: P2)

**Goal**: Enable filtering documents by date ranges and structured metadata for temporally-relevant retrieval

**Independent Test**: Store documents with timestamps and metadata, query by date ranges or metadata filters, verify correct subset returned

### Tests for User Story 3 (REQUIRED) ⚠️

- [ ] T054 [P] [US3] Create integration test for temporal_query in tests/integration/test_database.py - test date range filtering (created_at >= start AND created_at <= end) per spec.md acceptance scenarios
- [ ] T055 [P] [US3] Create integration test for metadata filtering in tests/integration/test_database.py - test JSONB where clause (metadata_["category"].astext == "research") per spec.md acceptance scenarios
- [ ] T056 [P] [US3] Create integration test for combined query in tests/integration/test_database.py - test date range + metadata + semantic search (AND logic) per spec.md acceptance scenario 3

### Implementation for User Story 3

- [ ] T057 [US3] Implement MemoryManager.temporal_query method in src/core/memory.py with date range filter (start_date, end_date), metadata filters, chronological ordering per contracts/README.md and FR-008
- [ ] T058 [US3] Add input validation to temporal_query in src/core/memory.py - validate end_date >= start_date per contracts/README.md
- [ ] T059 [US3] Add OpenTelemetry span attributes to temporal_query (start_date, end_date, filter_count, result_count) per FR-017
- [ ] T060 [US3] Extend semantic_search to support combined query (date range + metadata + vector similarity) in src/core/memory.py per spec.md acceptance scenario 3

**Checkpoint**: All user stories (US1, US2, US3, US4) should now work independently - agents have full memory capabilities plus observability

---

## Phase 7: User Story 5 - Run Database Migrations Safely (Priority: P3)

**Goal**: Provide repeatable database migrations with upgrade and rollback capability

**Independent Test**: Run alembic upgrade head on fresh database, verify schema creation, run alembic downgrade -1, confirm rollback

### Tests for User Story 5 (REQUIRED) ⚠️

- [ ] T061 [P] [US5] Create integration test for migration upgrade in tests/integration/test_migrations.py - test alembic upgrade head creates all tables with correct schema per spec.md acceptance scenario 1
- [ ] T062 [P] [US5] Create integration test for migration rollback in tests/integration/test_migrations.py - test alembic downgrade -1 drops tables and returns to previous state per spec.md acceptance scenario 2
- [ ] T063 [P] [US5] Create integration test for pgvector extension in tests/integration/test_migrations.py - test that migration enables pgvector extension per FR-029

### Implementation for User Story 5

- [ ] T064 [US5] Create initial Alembic migration 001_initial_schema.py in alembic/versions/ with sessions, messages, documents table creation per data-model.md and research.md section 5
- [ ] T065 [US5] Add pgvector extension setup to migration: CREATE EXTENSION IF NOT EXISTS vector per FR-029 and research.md section 5
- [ ] T066 [US5] Add HNSW index creation for documents.embedding in migration: CREATE INDEX USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64) per data-model.md and research.md section 4
- [ ] T067 [US5] Add GIN indexes for metadata_ columns in migration: CREATE INDEX USING gin (metadata_) for all three tables per data-model.md and FR-011
- [ ] T068 [US5] Add B-tree indexes in migration: session_id (messages), user_id (sessions), created_at (documents, messages) per data-model.md and FR-011
- [ ] T069 [US5] Add foreign key constraint in migration: messages.session_id REFERENCES sessions(id) ON DELETE CASCADE per data-model.md
- [ ] T070 [US5] Add check constraint in migration: messages.role IN ('user', 'assistant', 'system') per data-model.md
- [ ] T071 [US5] Implement downgrade function in migration to drop all tables and pgvector extension (with CASCADE) per FR-028 and research.md section 5
- [ ] T072 [US5] Test migration upgrade and downgrade on local Docker PostgreSQL per quickstart.md step 4

**Checkpoint**: Database migrations are repeatable and safe - schema can be deployed across environments without manual SQL

---

## Phase 8: Common Pydantic Models

**Purpose**: Create shared Pydantic models for inter-component contracts (not tied to specific user story)

- [ ] T073 [P] Create AgentResponse Pydantic model in src/models/common.py with fields (answer str, reasoning Optional[str], tool_calls list[dict], confidence float 0-1, timestamp datetime) per data-model.md
- [ ] T074 [P] Create ToolGapReport Pydantic model in src/models/common.py with fields (missing_tools list[str], attempted_task str, existing_tools_checked list[str], proposed_mcp_server Optional[str]) per data-model.md
- [ ] T075 [P] Create ApprovalRequest Pydantic model in src/models/common.py with fields (action_type str, action_description str, confidence float, risk_level RiskLevel enum, tool_name str, parameters dict, requires_immediate_approval bool, timeout_seconds Optional[int]) per data-model.md
- [ ] T076 [P] Add Pydantic field validators for AgentResponse.confidence (0.0 <= value <= 1.0) and ApprovalRequest.confidence (0.0 <= value <= 1.0) per data-model.md validation rules
- [ ] T077 [P] Create unit tests for AgentResponse, ToolGapReport, ApprovalRequest in tests/unit/test_models.py - test field validation, JSON serialization per data-model.md

**Checkpoint**: Common models ready for use by agents and workflows

---

## Phase 9: Health Check & Diagnostics

**Purpose**: Provide database connectivity health check for operations

- [ ] T078 Implement MemoryManager.health_check method in src/core/memory.py - test database connection, return {"status": "healthy", "postgres_version": "15.3", "pgvector_version": "0.5.1"} per contracts/README.md
- [ ] T079 Add PostgreSQL version query to health_check: SELECT version() per contracts/README.md
- [ ] T080 Add pgvector version query to health_check: SELECT extversion FROM pg_extension WHERE extname='vector' per contracts/README.md
- [ ] T081 Add OpenTelemetry span to health_check with attributes (status, postgres_version) per FR-017
- [ ] T082 Create integration test for health_check in tests/integration/test_database.py - test successful health check, database unreachable error per contracts/README.md

**Checkpoint**: Health check endpoint ready for monitoring and debugging

---

## Phase 10: Test Data & Fixtures

**Purpose**: Create reusable test data and fixtures for consistent testing

- [ ] T083 [P] Create sample_documents.py in tests/fixtures/ with 100+ sample documents, 1536-dim dummy embeddings, varied metadata (category, source, tags) per research.md section 9
- [ ] T084 [P] Add pytest fixture for clean database session in tests/fixtures/conftest.py - create tables before test, rollback after test per research.md section 9
- [ ] T085 [P] Add pytest fixture for Docker Compose service waits in tests/fixtures/conftest.py - wait for PostgreSQL healthy, Jaeger ready per research.md section 9 and quickstart.md
- [ ] T086 [P] Add pytest fixture for MemoryManager instance in tests/fixtures/conftest.py - initialize with test config per research.md section 9

**Checkpoint**: Test fixtures ready for comprehensive integration testing

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T087 [P] Create comprehensive README.md in repository root with architecture overview, setup instructions, quickstart commands per quickstart.md
- [ ] T088 [P] Add docstrings to all MemoryManager methods with full parameter descriptions, return types, raises exceptions per contracts/README.md
- [ ] T089 [P] Add type hints to all functions and methods per Article III.A (mypy strict mode)
- [ ] T090 [P] Run mypy strict type checking on src/ directory and fix any errors
- [ ] T091 [P] Run Ruff linter on src/ and tests/ directories and fix any issues
- [ ] T092 [P] Run Black formatter on src/ and tests/ directories for consistent code style
- [ ] T093 [P] Verify test coverage is ≥ 80% with pytest --cov=src --cov-fail-under=80 per Article III.A
- [ ] T094 [P] Add additional unit tests for edge cases (empty query string, dimension mismatch, connection errors) to reach 80%+ coverage per edge cases in spec.md
- [ ] T095 [P] Create quickstart validation script that runs through quickstart.md steps and verifies expected outputs
- [ ] T096 [P] Add performance benchmarks in tests/integration/ - verify <100ms conversation retrieval, <500ms semantic search per success criteria SC-001, SC-002
- [ ] T097 [P] Add concurrency test in tests/integration/ - verify 10 simultaneous sessions without deadlocks per SC-010
- [ ] T098 [P] Update contracts/README.md with any implementation-specific details discovered during development
- [ ] T099 [P] Create CONTRIBUTING.md with development workflow, testing strategy, commit conventions
- [ ] T100 [P] Create GitHub Actions CI workflow (or similar) with lint, type-check, test, coverage enforcement per Article III.A

**Checkpoint**: All polish tasks complete - project is production-ready for Phase 1

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) - can proceed after foundation ready
- **User Story 2 (Phase 4)**: Depends on Foundational (Phase 2) - can proceed in parallel with US1
- **User Story 4 (Phase 5)**: Depends on Foundational (Phase 2) - can proceed in parallel with US1, US2
- **User Story 3 (Phase 6)**: Depends on Foundational (Phase 2) + US2 (Phase 4) semantic_search method - extends semantic search
- **User Story 5 (Phase 7)**: Depends on Foundational (Phase 2) - can proceed in parallel with other user stories
- **Common Models (Phase 8)**: Can proceed in parallel with any user story (no dependencies)
- **Health Check (Phase 9)**: Depends on MemoryManager initialization (Phase 3, T028-T029)
- **Test Fixtures (Phase 10)**: Depends on SQLModel definitions (Phase 3, Phase 4) - should wait until US1, US2 models complete
- **Polish (Phase 11)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories ✅ MVP
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories (parallel with US1)
- **User Story 4 (P2)**: Can start after Foundational (Phase 2) - No dependencies on other stories (parallel with US1, US2)
- **User Story 3 (P2)**: Requires US2 (semantic_search method) - extends semantic search for combined queries
- **User Story 5 (P3)**: Can start after Foundational (Phase 2) - No dependencies on other stories (parallel with any)

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD approach to satisfy 80% coverage gate)
- SQLModel definitions before MemoryManager methods (T026-T027 before T030-T031)
- MemoryManager initialization (T028-T029) before any MemoryManager methods
- Core methods before extensions (semantic_search before combined query)
- Validation logic before tracing spans (ensure correctness before observability)

### Parallel Opportunities

**Setup Phase (Phase 1)** - All marked [P] can run in parallel:
- T003 (docker-compose.yml) || T004 (.env.example) || T005 (.gitignore) || T006 (README.md) || T007 (pytest.ini) || T008 (pyproject.toml)

**Foundational Phase (Phase 2)** - All marked [P] can run in parallel:
- T014 (config.py) || T015 (telemetry.py init) || T016 (decorator) || T017 (MessageRole enum) || T018 (RiskLevel enum)

**User Story 1 Tests** - All marked [P] can run in parallel:
- T022 (Session test) || T023 (Message test) || T024 (store_message test) || T025 (get_conversation_history test)

**User Story 1 Models** - All marked [P] can run in parallel:
- T026 (Session model) || T027 (Message model)

**User Story 2 Tests** - All marked [P] can run in parallel:
- T035 (Document test) || T036 (embedding validation test) || T037 (store_document test) || T038 (semantic_search test)

**User Story 4 Tests** - All marked [P] can run in parallel:
- T046 (decorator test) || T047 (trace export test)

**User Story 3 Tests** - All marked [P] can run in parallel:
- T054 (temporal_query test) || T055 (metadata filter test) || T056 (combined query test)

**User Story 5 Tests** - All marked [P] can run in parallel:
- T061 (upgrade test) || T062 (rollback test) || T063 (pgvector test)

**Common Models (Phase 8)** - All marked [P] can run in parallel:
- T073 (AgentResponse) || T074 (ToolGapReport) || T075 (ApprovalRequest) || T076 (validators) || T077 (tests)

**Test Fixtures (Phase 10)** - All marked [P] can run in parallel:
- T083 (sample_documents) || T084 (db fixture) || T085 (Docker wait fixture) || T086 (MemoryManager fixture)

**Polish (Phase 11)** - All marked [P] can run in parallel:
- All T087-T100 tasks are parallelizable (different files, no dependencies)

**Cross-Story Parallelization**:
- Once Foundational (Phase 2) completes, US1, US2, US4, US5 can ALL start in parallel
- US3 must wait for US2 semantic_search method (T041) before starting T060
- Common Models (Phase 8) can proceed in parallel with any user story

---

## Parallel Example: User Story 1

```bash
# After Foundational phase completes, launch all US1 tests together:
Parallel:
  - T022: Unit test for Session model validation
  - T023: Unit test for Message model validation
  - T024: Integration test for store_message
  - T025: Integration test for get_conversation_history

# Then launch models together:
Parallel:
  - T026: Create Session SQLModel
  - T027: Create Message SQLModel

# Sequential after models:
Sequential:
  - T028: Initialize async database engine
  - T029: Create async session factory
  - T030: Implement store_message method
  - T031: Implement get_conversation_history method
  - T032: Add field validators
  - T033: Add tracing to store_message
  - T034: Add tracing to get_conversation_history
```

---

## Parallel Example: Multiple User Stories

```bash
# After Foundational (Phase 2) completes, all P1 and P2 stories can start in parallel:

Developer A (US1 - Conversation):
  - T022-T034: Implement conversation storage and retrieval

Developer B (US2 - Semantic Search):
  - T035-T045: Implement document storage and semantic search

Developer C (US4 - Observability):
  - T046-T053: Enhance observability and tracing

Developer D (US5 - Migrations):
  - T061-T072: Create and test database migrations

# US3 starts after US2 completes (T041 semantic_search method):
Developer E (US3 - Temporal Queries):
  - T054-T060: Implement temporal and metadata filtering
```

---

## Implementation Strategy

### MVP First (User Story 1 Only) 🎯

1. Complete Phase 1: Setup (T001-T008)
2. Complete Phase 2: Foundational (T009-T021) - CRITICAL, blocks all stories
3. Complete Phase 3: User Story 1 (T022-T034)
4. **STOP and VALIDATE**: Run integration tests, verify conversation storage works independently
5. Deploy/demo conversation capability

**Deliverable**: Agents can store and retrieve conversation history (core MVP)

### Incremental Delivery (Prioritized User Stories)

1. **Foundation**: Setup (Phase 1) + Foundational (Phase 2) → T001-T021 ✅ Infrastructure ready
2. **MVP**: Add User Story 1 (Phase 3) → T022-T034 ✅ Test independently → Deploy (conversation storage)
3. **Increment 2**: Add User Story 2 (Phase 4) → T035-T045 ✅ Test independently → Deploy (+ semantic search)
4. **Increment 3**: Add User Story 4 (Phase 5) → T046-T053 ✅ Test independently → Deploy (+ observability)
5. **Increment 4**: Add User Story 3 (Phase 6) → T054-T060 ✅ Test independently → Deploy (+ temporal queries)
6. **Increment 5**: Add User Story 5 (Phase 7) → T061-T072 ✅ Test independently → Deploy (+ migrations)
7. **Polish**: Add Common Models (Phase 8) + Health Check (Phase 9) + Fixtures (Phase 10) + Polish (Phase 11) → Production ready

Each story adds value without breaking previous stories ✅

### Parallel Team Strategy

With multiple developers:

1. **Team completes Setup + Foundational together** (T001-T021)
2. **Once Foundational is done, parallel work begins**:
   - Developer A: User Story 1 (T022-T034) 🎯 MVP
   - Developer B: User Story 2 (T035-T045)
   - Developer C: User Story 4 (T046-T053)
   - Developer D: User Story 5 (T061-T072)
3. **After US2 completes**:
   - Developer E: User Story 3 (T054-T060) - extends US2
4. **Parallel polish**:
   - All developers: Common Models (T073-T077), Health Check (T078-T082), Fixtures (T083-T086), Polish (T087-T100)

**Benefit**: Maximum parallelization after foundational phase, independent testing per story

---

## Task Summary

**Total Tasks**: 100
- **Setup (Phase 1)**: 8 tasks (T001-T008)
- **Foundational (Phase 2)**: 13 tasks (T009-T021) - BLOCKS all user stories
- **User Story 1 (Phase 3)**: 13 tasks (T022-T034) 🎯 MVP
- **User Story 2 (Phase 4)**: 11 tasks (T035-T045)
- **User Story 4 (Phase 5)**: 8 tasks (T046-T053)
- **User Story 3 (Phase 6)**: 7 tasks (T054-T060)
- **User Story 5 (Phase 7)**: 12 tasks (T061-T072)
- **Common Models (Phase 8)**: 5 tasks (T073-T077)
- **Health Check (Phase 9)**: 5 tasks (T078-T082)
- **Test Fixtures (Phase 10)**: 4 tasks (T083-T086)
- **Polish (Phase 11)**: 14 tasks (T087-T100)

**Parallelizable Tasks**: 62 tasks marked [P]

**User Story Breakdown**:
- US1 (P1): 13 tasks 🎯 MVP
- US2 (P1): 11 tasks
- US3 (P2): 7 tasks
- US4 (P2): 8 tasks
- US5 (P3): 12 tasks

**MVP Scope (Recommended)**: Phase 1 (Setup) + Phase 2 (Foundational) + Phase 3 (User Story 1) = 34 tasks

---

## Notes

- [P] tasks = different files, no dependencies, can run in parallel
- [Story] label maps task to specific user story for traceability (US1, US2, US3, US4, US5)
- Each user story is independently completable and testable
- Tests written FIRST (TDD) to ensure they fail before implementation
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- US1 + US2 are both P1 (highest priority) - implement both for complete MVP
- US4 (observability) promoted to P2 and sequenced early - critical for debugging
- US3 depends on US2 - wait for semantic_search method before extending
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- Constitution compliance: All tasks reference relevant Articles (I.A, I.D, I.H, II.D, II.E, II.F, III.A, III.B, III.D)

