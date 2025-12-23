# Project Context & Decision Log

**Project**: Personal AI Assistant System (PAIAS)  
**Current Phase**: Phase 1 — Foundation / Vertical Slice  
**Phase Intent**: Deliver an end-to-end slice (UI → Workflow → Agent → Memory) to prove the architecture works and delivers value. 
**Governed By**: `constitution.md` v2.1. 
**Date**: 2025-12-22

---

## 1. Current Status (Where We Are Now)

Phase 1 core memory layer is implemented and passing tests (async SQLModel + asyncpg + pgvector, OpenTelemetry tracing). Docker Compose (PostgreSQL 15 + Jaeger) is required for local runs and tests; coverage gate enforced at 80%.

- **Orchestration**: Windmill as primary orchestrator for simple DAG; LangGraph embedded in Windmill step for retry/refine loops. 
- **Reasoning**: LangGraph inside Windmill; Pydantic AI for agent capabilities. 
- **Agent**: `ResearcherAgent` built with Pydantic AI. 
- **Memory**: PostgreSQL + pgvector running via Docker Compose; Alembic migrations in place.

---

## 2. Non-Negotiable Direction (Constitutional Rules)

All work must strictly adhere to the project constitution. Key principles include:

- **Article I: Technology Stack**: The stack is fixed. All backend logic must use Python 3.11+.  Orchestration is a hybrid model with Windmill as the primary and LangGraph for complex in-step reasoning.  Pydantic AI is the *only* framework for building atomic agent capabilities.  Memory is PostgreSQL-first. 

- **Article II: Architectural Principles**: The system must be built with a "Vertical Slice" approach.  All tool integrations *must* use the Model Context Protocol (MCP).  Everything must be observable via OpenTelemetry.  A "Human-in-the-Loop" safety model is mandatory from day one, with actions categorized by risk. 

- **Article III: Quality & Operational Standards**: All code requires >80% unit test coverage.  No Personally Identifiable Information (PII) is to be stored without explicit encryption.  Tool execution must be isolated in sandboxes (e.g., containers). 

- **Article IV: Governance & Workflow**: Development must follow Spec-Driven Development (SDD).  Agents must be capable of "Tool Gap Detection" and output a structured request for human developers when a required tool is missing. 

---

## 3. Key Decisions & Rationale (Log)

This section records *why* decisions were made, providing context for future phases. Items marked 🟢 are now implemented/validated in Phase 1.

- **Decision (Orchestration)**: **Windmill + LangGraph** was chosen over a single framework. 🟢 validated via workflow plan; implementation remains planned for later slices.
  - **Rationale**: Windmill provides enterprise-grade DAG orchestration, scheduling, and observability, while LangGraph excels at complex, cyclical reasoning needed for agentic loops. 

- **Decision (Memory)**: **PostgreSQL with pgvector** for Phase 1-2. 🟢 implemented with Alembic migration `001_initial_schema`.
  - **Rationale**: Single reliable datastore, sufficient for semantic search; avoids premature multi-store complexity.
  - **Operational note**: Migration fixes `Vector(1536)` with HNSW (`m=16`, `ef_construction=64`) and GIN indexes on JSONB metadata. Changing `vector_dimension` now requires a new migration to keep schema and settings aligned.
  - **ADR**: See `docs/adr/0001-memory-layer.md` for stack, tracing defaults, and migration constraints.

- **Decision (Agents)**: **Pydantic AI** for agent capabilities. 🟢 adopted.
  - **Rationale**: Type safety, model-agnostic, MCP-friendly separation between capabilities and orchestration. 

- **Decision (UI)**: **Streamlit** for Phase 1-2. 
  - **Rationale**: Python-native, streaming-friendly, enforces headless API boundary, easy to surface OTel/Windmill updates.
  - **Trade-off**: Not production-grade for multi-user; migration to React/Next.js or LibreChat planned for Phase 3. 

---

## 4. Open Questions & Blockers (To Be Resolved in Phase 1)

- **Flagship Workflow**: What is the definitive "DailyTrendingResearch" workflow for the Phase 1 demo? What specific sources will it use, and what is the exact output format?
- **Risk Categories**: What is the initial, concrete list of "reversible," "reversible-with-delay," and "irreversible" actions for the Human-in-the-Loop policy?
- **Tooling**: Which three MCP servers will be implemented first to support the flagship workflow? (e.g., `@web_search`, `@filesystem`, `@email`). 
- **UI path**: Confirm when to transition from Streamlit to production UI (React/Next.js or LibreChat) based on Phase 1 learnings.

---

## 5. Operational Notes from Implementation

- **Memory API**: `store_message` auto-creates sessions with `user_id="auto-created"` when missing; `get_conversation_history` returns chronological order by reversing a DESC query to keep indexes efficient. Content and roles are validated before writes; metadata stored as JSONB. 
- **Semantic search & filters**: `semantic_search` performs cosine ordering on `embedding`, supports metadata/date filters, and records timing metrics; `temporal_query` validates date ranges and applies metadata filters.
- **Tracing**: All MemoryManager methods wrap in `@trace_memory_operation`, setting `operation.type`, `operation.success`, `db.system=postgresql`, and recording exceptions. Default OTLP gRPC exporter; `otel_exporter_otlp_endpoint="memory"` switches tests to an in-memory exporter. Sampling is 100%.
- **Health check**: Queries Postgres version and pgvector extension version; returns `{"status": "healthy", ...}` and records span attributes.
- **Dependencies**: Docker Compose services (PostgreSQL 15 + pgvector, Jaeger) must be running for integration tests; coverage gate set at 80% in pytest config. 

## 6. Next Review Cycle

A formal review of this context and Phase 1 progress will occur upon the successful completion of the first end-to-end workflow run.
