# Project Context & Decision Log

**Project**: Personal AI Assistant System (PAIAS)  
**Current Phase**: Phase 1 — Foundation / Vertical Slice  
**Phase Intent**: Deliver an end-to-end slice (UI → Workflow → Agent → Memory) to prove the architecture works and delivers value. 
**Governed By**: `constitution.md` v2.1. 
**Date**: 2025-12-21

---

## 1. Current Status (Where We Are Now)

We are executing **Phase 1 (Foundation)**.  The primary goal is to build the first "vertical slice" of the system, demonstrating a complete, working loop from user input to a useful, automated output.

- **Orchestration**: Windmill is being deployed as the primary orchestrator for a simple DAG (Directed Acyclic Graph) workflow. 
- **Reasoning**: LangGraph will be used as a library *inside* a Windmill step to handle a research task that requires a retry/refine loop. 
- **Agent**: The first agent, `ResearcherAgent`, is being built using Pydantic AI. 
- **Memory**: A PostgreSQL database with the `pgvector` extension is being set up to store conversation history and initial document embeddings. 

---

## 2. Non-Negotiable Direction (Constitutional Rules)

All work must strictly adhere to the project constitution. Key principles include:

- **Article I: Technology Stack**: The stack is fixed. All backend logic must use Python 3.11+.  Orchestration is a hybrid model with Windmill as the primary and LangGraph for complex in-step reasoning.  Pydantic AI is the *only* framework for building atomic agent capabilities.  Memory is PostgreSQL-first. 

- **Article II: Architectural Principles**: The system must be built with a "Vertical Slice" approach.  All tool integrations *must* use the Model Context Protocol (MCP).  Everything must be observable via OpenTelemetry.  A "Human-in-the-Loop" safety model is mandatory from day one, with actions categorized by risk. 

- **Article III: Quality & Operational Standards**: All code requires >80% unit test coverage.  No Personally Identifiable Information (PII) is to be stored without explicit encryption.  Tool execution must be isolated in sandboxes (e.g., containers). 

- **Article IV: Governance & Workflow**: Development must follow Spec-Driven Development (SDD).  Agents must be capable of "Tool Gap Detection" and output a structured request for human developers when a required tool is missing. 

---

## 3. Key Decisions & Rationale (Log)

This section records *why* decisions were made, providing context for future phases.

- **Decision (Orchestration)**: **Windmill + LangGraph** was chosen over a single framework.
  - **Rationale**: Windmill provides enterprise-grade DAG orchestration, scheduling, and observability, while LangGraph excels at the complex, cyclical reasoning needed for agentic loops. This hybrid model provides the best of both worlds. 

- **Decision (Memory)**: **PostgreSQL with pgvector** was chosen for Phase 1-2 instead of a dedicated vector database.
  - **Rationale**: This simplifies the initial architecture to a single, reliable datastore. It is sufficient for initial semantic search needs and avoids the premature complexity of a multi-store setup. A migration path to specialized stores is defined in the constitution for when scale demands it. 

- **Decision (Agents)**: **Pydantic AI** was selected as the agent building block.
  - **Rationale**: It enforces type safety, is model-agnostic, and is natively compatible with MCP. It defines the "atomic unit" of capability, separating the agent's logic from the system's orchestration layer. 

- **Decision (UI)**: **Streamlit** was chosen for Phase 1-2 instead of LibreChat or Windmill Native Apps.
  - **Rationale**: 
    - Python-native: No JavaScript build chain required for Phase 1 velocity
    - Streaming-ready: Native `st.write_stream` handles token-by-token output with zero complexity
    - Decoupled: Forces us to build a clean API contract between UI and Windmill workflows, proving the backend is truly headless
    - Observability-friendly: Easy to render OpenTelemetry logs and Windmill step updates in real-time sidebars
  - **Trade-off**: Streamlit is not production-grade for multi-user scenarios (lacks robust auth, session isolation). Migration to React/Next.js or LibreChat planned for Phase 3 when multi-user demand justifies the investment.
  - **Constitutional Reference**: Added as Article I.F (User Interface Technology)

---

## 4. Open Questions & Blockers (To Be Resolved in Phase 1)

- **Flagship Workflow**: What is the definitive "DailyTrendingResearch" workflow for the Phase 1 demo? What specific sources will it use, and what is the exact output format?
- **Risk Categories**: What is the initial, concrete list of "reversible," "reversible-with-delay," and "irreversible" actions for the Human-in-the-Loop policy?
- **Tooling**: Which three MCP servers will be implemented first to support the flagship workflow? (e.g., `@web_search`, `@filesystem`, `@email`). 

---

## 5. Next Review Cycle

A formal review of this context and Phase 1 progress will occur upon the successful completion of the first end-to-end workflow run.
