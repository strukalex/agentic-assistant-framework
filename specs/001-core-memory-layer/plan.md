# Implementation Plan: Core Foundation and Memory Layer

**Branch**: `001-core-memory-layer` | **Date**: 2025-12-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-core-memory-layer/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

This feature establishes the foundational data persistence and observability infrastructure for the PAIAS Phase 1 vertical slice. It includes:

1. **PostgreSQL + pgvector database schema** for sessions, messages, and documents with configurable vector embeddings (default 1536 for OpenAI Ada-002)
2. **MemoryManager abstraction layer** providing async methods for storing/retrieving conversation history and semantic document search
3. **Base Pydantic models** (AgentResponse, ToolGapReport, ApprovalRequest, RiskLevel) for inter-component contracts
4. **OpenTelemetry instrumentation** with Jaeger exporter for full observability of all database operations
5. **Docker Compose infrastructure** for local development with PostgreSQL + Jaeger
6. **Alembic migrations** for repeatable schema management

**Technical Approach**: SQLModel (unified Pydantic/ORM models) + asyncpg driver + OpenTelemetry decorators + Docker-first deployment. All memory operations are async and fully traced. Agents interact only through the MemoryManager abstraction—no direct database driver imports allowed (Constitution Article II.E).

## Technical Context

**Language/Version**: Python 3.11+ *(non-negotiable; see Constitution Article I.A)*  
**Primary Dependencies**: SQLModel 0.0.14+, asyncpg 0.30+, Pydantic 2.0+, opentelemetry-sdk 1.20+, opentelemetry-exporter-otlp 1.20+, alembic 1.13+ *(Article I.H)*  
**Storage**: PostgreSQL 15+ with pgvector extension 0.5.0+ *(Article I.D)*  
**Tool Integration**: Not applicable for Phase 1 (memory layer is internal infrastructure; MCP integration deferred to agent layer)  
**UI Layer**: Not applicable (memory layer is backend infrastructure)  
**Primary LLM**: Not applicable (memory layer stores embeddings but doesn't generate them)  
**Testing**: pytest 7.0+ + pytest-cov 4.0+ + pytest-asyncio 0.21+; **minimum 80% coverage** *(Article III.A)*  
**Target Platform**: Linux x86_64 (Docker containerized for cross-platform compatibility)  
**Project Type**: Core infrastructure library (Python package with async API)  
**Performance Goals**: 
- <100ms for conversation history retrieval (up to 1000 messages)
- <500ms for semantic search (top-10 from 10k documents)
- <50ms trace span overhead per database operation
**Constraints**: 
- All database operations must be async (asyncio-compatible)
- Memory abstraction must prevent agents from importing database drivers
- Embedding dimension is configurable via settings (`vector_dimension`, default 1536) and paired `embedding_model_name`
- 100% sampling rate for OpenTelemetry traces (Phase 1 only)
**Scale/Scope**: 
- Phase 1: 10k documents, 100 sessions, 10k messages (single-user development)
- Designed to scale to 1M+ documents in Phase 2 with proper indexing

## Constitution Check

*GATE: Must pass before research begins. Re-check after design phase.*

**Source of truth**: `.specify/memory/constitution.md` (v2.0+)  
**Project context**: `.specify/memory/project-context.md` (current phase, key decisions, open questions)

### Constitutional Compliance Checklist (MUST)

- [x] **Article I — Non-Negotiable Technology Stack**: Implementation uses the approved stack:
  - [x] **Python 3.11+**
  - [N/A] **Orchestration**: Not applicable (memory layer is infrastructure; orchestration happens at agent/workflow level)
  - [N/A] **Agents**: Not applicable (memory layer is consumed by agents, not an agent itself)
  - [x] **Memory**: PostgreSQL + pgvector (PostgreSQL is source of truth; memory abstraction layer required)
  - [N/A] **Tools**: Not applicable (memory layer is internal infrastructure, not a tool)
  - [N/A] **UI**: Not applicable (memory layer is backend infrastructure)
  - [N/A] **Primary model**: Not applicable (memory layer stores embeddings but doesn't call LLMs)

- [x] **Article II — Architectural Principles (all 7)**: Plan explicitly respects:
  - [x] Vertical-slice delivery (memory layer + tests + docker compose = complete deliverable)
  - [x] Pluggable orchestration (memory abstraction decouples from any specific agent framework)
  - [N/A] Human-in-the-loop by default (not applicable; memory layer has no user-facing actions)
  - [x] Observable everything (OpenTelemetry spans for all database operations)
  - [x] Multi-storage memory abstraction (MemoryManager abstraction prevents direct DB driver imports)
  - [x] Isolation & safety boundaries (async-compatible; Docker containerized for Phase 1)
  - [N/A] Tool gap detection & self-extension (not applicable; memory layer is not an agent)

- [x] **Article III — Operational Standards**:
  - [x] Tests + CI enforce **≥ 80% coverage** (unit + integration tests for all MemoryManager methods)
  - [x] Async I/O for DB operations (asyncpg driver; all MemoryManager methods are async)
  - [x] OpenTelemetry instrumentation for database operations (custom decorators: @trace_memory_operation)

### If any gate fails

- Document the violation in this plan (with rationale + mitigation) and follow **Article V** amendment/approval process before proceeding.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── core/
│   ├── __init__.py
│   ├── memory.py              # MemoryManager class with async methods
│   ├── telemetry.py           # OpenTelemetry setup + decorators
│   └── config.py              # Environment variable configuration
├── models/
│   ├── __init__.py
│   ├── common.py              # AgentResponse, ToolGapReport, ApprovalRequest, RiskLevel
│   ├── session.py             # Session SQLModel
│   ├── message.py             # Message SQLModel
│   └── document.py            # Document SQLModel (with pgvector column)

tests/
├── unit/
│   ├── test_memory.py         # Unit tests for MemoryManager methods
│   ├── test_telemetry.py      # Unit tests for tracing decorators
│   └── test_models.py         # Unit tests for Pydantic validation
├── integration/
│   ├── test_database.py       # Integration tests with PostgreSQL
│   ├── test_semantic_search.py # Integration tests for vector queries
│   └── test_migrations.py     # Integration tests for Alembic migrations
└── fixtures/
    ├── sample_documents.py    # Test data with embeddings
    └── conftest.py            # Pytest fixtures for DB setup

alembic/
├── versions/
│   └── 001_initial_schema.py  # Initial migration (sessions, messages, documents)
├── env.py                     # Alembic environment config
└── script.py.mako             # Migration template

docker-compose.yml             # PostgreSQL + Jaeger containers
.env.example                   # Example environment variables
pyproject.toml                 # Poetry/pip dependencies + tool config
```

**Structure Decision**: Single project structure (Option 1) is appropriate because:
- This is a foundational library consumed by other components (agents, workflows)
- No frontend/backend split required (pure backend infrastructure)
- SQLModel models serve as both Pydantic schemas AND ORM models (single source of truth)
- Tests are organized by type (unit vs integration) rather than by feature

## Complexity Tracking

**No constitutional violations**: All requirements comply with Constitution v2.1. No complexity justification required.

---

## Post-Design Constitutional Compliance Review

**Date**: 2025-12-21  
**Status**: ✅ PASSED (No violations)

After completing Phase 0 (Research) and Phase 1 (Design & Contracts), we re-evaluated constitutional compliance:

### Re-Validated Requirements

- [x] **Article I.A (Python 3.11+)**: ✅ All code uses Python 3.11+ with asyncio
- [x] **Article I.D (PostgreSQL + pgvector)**: ✅ SQLModel + asyncpg + pgvector extension
- [x] **Article I.H (Supporting Libraries)**: ✅ Pydantic 2.0+, pytest, OpenTelemetry, asyncpg
- [x] **Article II.D (Observable Everything)**: ✅ OpenTelemetry decorators for all database operations
- [x] **Article II.E (Memory Abstraction)**: ✅ MemoryManager prevents direct DB driver imports
- [x] **Article III.A (Testing)**: ✅ 80%+ coverage target with pytest + pytest-asyncio
- [x] **Article III.B (Async Best Practices)**: ✅ All I/O operations use async/await
- [x] **Article III.D (Database Migrations)**: ✅ Alembic for schema management

### Design Decisions Validated

1. **SQLModel for unified models**: ✅ Single source of truth (Pydantic + ORM)
2. **HNSW vector index**: ✅ Optimal for Phase 1 scale (<100k documents)
3. **Custom OpenTelemetry decorators**: ✅ Fine-grained control over span attributes
4. **Docker Compose infrastructure**: ✅ One-command local development setup
5. **Pydantic Settings for config**: ✅ Type-safe environment variable management

### No New Violations Introduced

All design artifacts (research.md, data-model.md, contracts/, quickstart.md) comply with constitutional requirements. No amendments required.

**Conclusion**: Implementation may proceed to `/speckit.tasks` phase.

---

## Deliverables Summary

### Phase 0: Research (COMPLETED)

**File**: `specs/001-core-memory-layer/research.md`

✅ Resolved 10 technical unknowns:
1. SQLModel + pgvector integration pattern
2. Async database driver configuration (asyncpg)
3. OpenTelemetry instrumentation strategy
4. pgvector index selection (HNSW vs IVFFlat)
5. Alembic migration strategy
6. Environment configuration (Pydantic Settings)
7. Docker Compose infrastructure
8. Session lifecycle management (auto-creation)
9. Test strategy (pytest + pytest-asyncio)
10. Embedding validation (Pydantic field validators)

### Phase 1: Design & Contracts (COMPLETED)

**Files**:
- `specs/001-core-memory-layer/data-model.md` - Complete database schema + entity relationships
- `specs/001-core-memory-layer/contracts/README.md` - API contracts with JSON schemas + usage examples
- `specs/001-core-memory-layer/quickstart.md` - Step-by-step developer guide

✅ Design artifacts include:
- 3 database tables (sessions, messages, documents)
- 8 MemoryManager async methods
- 6 Pydantic models (Session, Message, Document, AgentResponse, ToolGapReport, ApprovalRequest)
- Complete indexing strategy (B-tree, GIN, HNSW)
- Docker Compose setup (PostgreSQL + Jaeger)
- Comprehensive usage examples

### Phase 1: Agent Context Update (COMPLETED)

✅ Updated `.cursor/rules/specify-rules.mdc` with:
- Python 3.11+ language requirement
- SQLModel, asyncpg, Pydantic, OpenTelemetry dependencies
- PostgreSQL 15+ with pgvector extension

---

## Next Steps

This plan is now **READY** for task breakdown. Run:

```bash
/speckit.tasks
```

This will generate `specs/001-core-memory-layer/tasks.md` with:
- Granular implementation tasks (file-level)
- Acceptance criteria per task
- Dependency graph
- Estimated complexity

---

## Plan Metadata

**Created**: 2025-12-21  
**Feature Branch**: `001-core-memory-layer`  
**Phase**: Phase 0 & Phase 1 Complete  
**Constitutional Status**: ✅ Fully Compliant  
**Next Command**: `/speckit.tasks`
