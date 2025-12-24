# Implementation Plan: DailyTrendingResearch Workflow

**Branch**: `003-daily-research-workflow` | **Date**: 2025-12-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-daily-research-workflow/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build the DailyTrendingResearch Workflow using Windmill as the primary orchestrator with LangGraph embedded for cyclical reasoning. The workflow accepts a research topic, executes iterative Plan→Research→Critique→Refine loops via LangGraph (up to 5 iterations), integrates the existing ResearcherAgent (Spec 002), stores results via MemoryManager (Spec 001), and implements human-in-the-loop approval gates for REVERSIBLE_WITH_DELAY actions. Complete OpenTelemetry instrumentation enables end-to-end observability.

## Technical Context

**Language/Version**: Python 3.11+ *(non-negotiable; see Constitution Article I.A)*
**Primary Dependencies**:
- Windmill (DAG orchestration, approval gates, scheduled execution)
- LangGraph (cyclical reasoning embedded in Windmill steps)
- Pydantic AI (agent unit via existing ResearcherAgent)
- FastAPI + Pydantic (API validation)

**Storage**: PostgreSQL 15+ + pgvector via existing MemoryManager (`src/core/memory.py`)
**Tool Integration**: MCP via existing setup (`src/mcp_integration/setup.py`) — Open-WebSearch for search
**UI Layer**: Streamlit for Phase 1-2 (API-triggered workflows; no direct agent calls)
**Primary LLM**: DeepSeek 3.2 via Azure AI Foundry (via `src/core/llm.py`)
**Testing**: pytest + pytest-cov; **minimum 80% coverage** *(Article III.A)*
**Target Platform**: Linux server with Docker (Windmill workers)
**Project Type**: Workflow orchestration with embedded agentic reasoning

**Performance Goals**:
- Research report delivery: ≤10 minutes (95th percentile) per spec SC-001
- Approval gate activation: ≤2 seconds per spec SC-003
- Concurrent workflow capacity: 10 workflows per spec SC-006

**Constraints**:
- Max 5 LangGraph iterations per research run (hard limit, FR-005)
- Subprocess isolation: 1 CPU core, 2GB memory per agent execution (FR-010)
- Approval timeout: 5 minutes ± 10 seconds (FR-007, SC-005)

**Scale/Scope**:
- Single-user Phase 1 deployment (multi-user deferred to Phase 2+)
- Integration with existing: ResearcherAgent, MemoryManager, telemetry, llm utilities

## Constitution Check

*GATE: Must pass before research begins. Re-check after design phase.*

**Source of truth**: `.specify/memory/constitution.md` (v2.3)
**Project context**: `.specify/memory/project-context.md` (Phase 1 — Foundation / Vertical Slice)

### Constitutional Compliance Checklist (MUST)

- [x] **Article I — Non-Negotiable Technology Stack**: Implementation uses the approved stack:
  - [x] **Python 3.11+** — All workflow code uses Python 3.11+
  - [x] **Orchestration**: Pattern-driven selection (Article I.B) — Windmill for DAG/linear workflow steps, LangGraph for cyclical research reasoning loop (Plan→Research→Critique→Refine)
  - [x] **Agents**: Pydantic AI as the atomic agent unit — Uses existing ResearcherAgent from Spec 002
  - [x] **Memory**: PostgreSQL + pgvector — Uses existing MemoryManager abstraction (`src/core/memory.py`)
  - [x] **Tools**: MCP-only tool discovery/execution — Uses existing MCP setup (`src/mcp_integration/setup.py`)
  - [x] **UI**: Streamlit for Phase 1-2 — Workflow triggered via API/webhook; UI calls Windmill (no direct agent calls per Article I.F)
  - [x] **Primary model**: DeepSeek 3.2 via Azure AI Foundry — Uses `src/core/llm.py` get_azure_model()

- [x] **Article II — Architectural Principles (all 9)**: Plan explicitly respects:
  - [x] Vertical-slice delivery — Complete flow: topic input → orchestration → LangGraph reasoning → memory storage → report output
  - [x] Pluggable orchestration — ResearcherAgent remains framework-agnostic; LangGraph embedded in Windmill steps
  - [x] Human-in-the-loop by default — Windmill native approval system for REVERSIBLE_WITH_DELAY actions; 5-min timeout
  - [x] Observable everything — OpenTelemetry spans for workflow steps, LangGraph nodes, agent tools, memory ops
  - [x] Multi-storage memory abstraction — Uses MemoryManager interface; no direct asyncpg imports in workflow code
  - [x] Isolation & safety boundaries — Subprocess isolation via Windmill worker resource limits (1 CPU, 2GB)
  - [x] Tool gap detection & self-extension — Pre-execution ToolGapDetector check (existing from Spec 002)
  - [x] Unified telemetry architecture — Uses `src/core/telemetry.py` decorators only (trace_agent_operation, trace_tool_call, trace_memory_operation)
  - [x] Shared LLM utilities & code reuse — Uses `src/core/llm.py` for model setup per Article II.I

- [x] **Article III — Operational Standards**:
  - [x] Tests + CI enforce **≥ 80% coverage** — Workflow tests with mocked Windmill + LangGraph nodes
  - [x] Async I/O for DB, MCP calls, external APIs — Existing async patterns from Spec 001/002
  - [x] OpenTelemetry instrumentation — Spans for each LangGraph node + Windmill step + approval events

### If any gate fails

No gate failures identified. All constitutional requirements satisfied by design.

## Project Structure

### Documentation (this feature)

```text
specs/003-daily-research-workflow/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output - research findings
├── data-model.md        # Phase 1 output - entity definitions
├── quickstart.md        # Phase 1 output - developer guide
├── contracts/           # Phase 1 output - API schemas
│   └── workflow-api.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── core/
│   ├── llm.py              # Shared LLM utilities (EXISTING - Article II.I)
│   ├── telemetry.py        # Unified telemetry (EXISTING - Article II.H)
│   ├── memory.py           # MemoryManager (EXISTING - Spec 001)
│   ├── risk_assessment.py  # Risk categorization (EXISTING)
│   └── tool_gap_detector.py # Tool gap detection (EXISTING)
├── agents/
│   └── researcher.py       # ResearcherAgent (EXISTING - Spec 002)
├── workflows/              # NEW - Spec 003
│   ├── __init__.py
│   ├── research_graph.py   # LangGraph state machine (Plan→Research→Critique→Refine→Finish)
│   ├── nodes/              # LangGraph node implementations
│   │   ├── __init__.py
│   │   ├── plan.py
│   │   ├── research.py
│   │   ├── critique.py
│   │   ├── refine.py
│   │   └── finish.py
│   └── report_formatter.py # Markdown report generation
├── models/
│   ├── research_state.py   # ResearchState Pydantic model (NEW) - single source of truth
│   ├── research_report.py  # ResearchReport model (NEW)
│   ├── approval_request.py # ApprovalRequest model (NEW)
│   └── ... (EXISTING models)
├── mcp_integration/
│   └── setup.py            # MCP tools initialization (EXISTING)
└── windmill/               # NEW - Windmill workflow definitions
    ├── __init__.py
    ├── daily_research.py   # Main workflow script
    └── approval_handler.py # Approval gate integration

tests/
├── unit/
│   ├── test_research_graph.py  # LangGraph node tests
│   ├── test_research_state.py  # State model tests
│   └── test_report_formatter.py
├── integration/
│   ├── test_workflow_e2e.py    # End-to-end workflow tests
│   └── test_approval_gates.py  # Approval system tests
└── contract/
    └── test_workflow_api.py    # API contract validation
```

**Structure Decision**: Extends existing single-project structure. New `src/workflows/` module for LangGraph orchestration logic, `src/windmill/` for Windmill-specific workflow scripts. Reuses all existing core modules (memory, telemetry, llm, agents).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. All complexity within constitutional bounds:
- Windmill + LangGraph hybrid is explicitly approved by Constitution Article I.B
- All new code integrates with existing shared utilities (llm.py, telemetry.py, memory.py)
