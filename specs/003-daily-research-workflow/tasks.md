---
description: "Task list for implementing Spec 003: DailyTrendingResearch Workflow"
---

# Tasks: DailyTrendingResearch Workflow (Spec 003)

**Input**: Design documents from `/specs/003-daily-research-workflow/`
**Prerequisites**: `plan.md` (required), `spec.md` (required for user stories), `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Tests are **REQUIRED** to meet the project constitution’s quality gate (**≥ 80% coverage**). Any exception MUST be justified and approved via **Article V (Amendment Process)** in `.specify/memory/constitution.md`.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `- [ ] T### [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[US#]**: Which user story this task belongs to (US1/US2/US3)
- Every task includes at least one exact file path

## Constitution-driven cross-cutting requirements *(mandatory)*

**Source of truth**: `.specify/memory/constitution.md` (v2.3)
**Project context**: `.specify/memory/project-context.md`

Non-negotiables to satisfy while implementing tasks below:
- **Article I**: Python 3.11+, Windmill + LangGraph hybrid, Pydantic AI (agents), PostgreSQL+pgvector via MemoryManager, MCP-only tools, Streamlit (Phase 1-2), DeepSeek 3.2 via Azure AI Foundry
- **Article II**: Human-in-the-loop by default, observable everything (OpenTelemetry), pluggable orchestration, unified telemetry (`src/core/telemetry.py`), shared LLM utilities (`src/core/llm.py`)
- **Article III**: Async I/O for DB/tool calls, Alembic migrations for schema changes, **coverage ≥ 80%**

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add missing dependencies and scaffold new modules for Spec 003 (no business logic yet).

- [ ] T001 Update runtime deps for Spec 003 in `pyproject.toml` (add `fastapi`, `uvicorn`, `langgraph`, `wmill`, `httpx`)
- [ ] T002 Update dev/test deps in `pyproject.toml` (add `pyyaml` for OpenAPI contract parsing in tests)
- [ ] T003 [P] Create workflow package scaffolding in `src/workflows/__init__.py`, `src/workflows/nodes/__init__.py`
- [ ] T004 [P] Create Windmill package scaffolding in `src/windmill/__init__.py`
- [ ] T005 [P] Create API package scaffolding in `src/api/__init__.py`, `src/api/routes/__init__.py`, `src/api/schemas/__init__.py`
- [ ] T006 Create FastAPI app entrypoint in `src/api/app.py` (app factory + router inclusion + basic `/healthz`)
- [ ] T007 Add API run helper for local dev in `src/cli/run_api.py` (documented uvicorn command + env loading)
- [ ] T008 Update developer docs to mention API runner in `specs/003-daily-research-workflow/quickstart.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types, config, and adapters that all user stories build on. **Blocks all user story work.**

- [ ] T009 Extend settings for Windmill integration in `src/core/config.py` (add `windmill_base_url`, `windmill_workspace`, `windmill_token`, `approval_timeout_seconds`)
- [ ] T010 [P] Define `SourceReference` Pydantic model in `src/models/source_reference.py` (validate `snippet<=1000`, URL format)
- [ ] T011 [P] Define `PlannedAction` Pydantic model in `src/models/planned_action.py` (fields per `data-model.md`, includes `risk_level`)
- [ ] T012 [P] Define `ResearchState` Pydantic model in `src/models/research_state.py` (topic/user_id validation, iteration/max_iterations cap at 5, planned_actions)
- [ ] T013 [P] Define `ResearchReport` Pydantic model in `src/models/research_report.py` (markdown/report fields + metadata)
- [ ] T014 [P] Define `ApprovalRequest` Pydantic model in `src/models/approval_request.py` (timeout_at rules, status enum)
- [ ] T015 Create contract-aligned API schemas in `src/api/schemas/workflow_api.py` (CreateRunRequest/Response, RunStatusResponse, ReportResponse, ErrorResponse)
- [ ] T016 Create Windmill API client adapter in `src/windmill/client.py` (trigger flow, fetch job status, fetch job result) using `httpx`
- [ ] T017 Create workflow module skeleton in `src/workflows/research_graph.py` (build/compile graph functions; no node logic yet)
- [ ] T018 Create report formatting module skeleton in `src/workflows/report_formatter.py` (Markdown layout per FR-008)
- [ ] T019 Add foundational unit tests for new models in `tests/unit/test_daily_research_models.py` (validation rules from `data-model.md`)

**Checkpoint**: Foundation ready — user story implementation can begin.

---

## Phase 3: User Story 1 — Execute Deep Research on a Topic (Priority: P1) 🎯 MVP

**Goal**: Start a workflow run from API, execute Plan→Research→Critique→Refine→Finish loop (max 5), store report via `MemoryManager`, and return a Markdown report with ≥3 sources when available.

**Independent Test**: Submit a topic + user_id via API (`POST /v1/research/workflows/daily-trending-research/runs`), then poll status until completed, then fetch report; verify Markdown + sources list, and verify storage metadata includes `topic`, `user_id`, `iteration_count`.

### Tests for User Story 1 (REQUIRED) ⚠️

- [ ] T020 [P] [US1] Add OpenAPI contract test for workflow endpoints in `tests/contract/test_workflow_api_contract.py` (parse `specs/003-daily-research-workflow/contracts/workflow-api.yaml`)
- [ ] T021 [P] [US1] Add unit tests for report formatting in `tests/unit/test_report_formatter.py` (sections + citations + metadata)
- [ ] T022 [P] [US1] Add unit tests for graph iteration cap in `tests/unit/test_research_graph_iteration_limit.py` (hard stop at 5 per FR-005)
- [ ] T023 [P] [US1] Add integration test for end-to-end graph run with mocked agent + memory in `tests/integration/test_daily_research_graph_e2e.py`

### Implementation for User Story 1

- [ ] T024 [P] [US1] Implement Plan node in `src/workflows/nodes/plan.py` (derive a research plan from topic; update `ResearchState.plan`)
- [ ] T025 [P] [US1] Implement Research node in `src/workflows/nodes/research.py` (invoke `src/agents/researcher.py:run_researcher_agent`, extract sources, update `refined_answer`)
- [ ] T026 [P] [US1] Implement Critique node in `src/workflows/nodes/critique.py` (detect missing sources/quality issues; decide loop vs finish)
- [ ] T027 [P] [US1] Implement Refine node in `src/workflows/nodes/refine.py` (increment iteration, adjust plan/queries based on critique)
- [ ] T028 [P] [US1] Implement Finish node in `src/workflows/nodes/finish.py` (build `ResearchReport`, store via `src/core/memory.py:MemoryManager`, return memory doc id)
- [ ] T029 [US1] Implement LangGraph assembly in `src/workflows/research_graph.py` (StateGraph wiring + conditional edge + max-5 enforcement)
- [ ] T030 [US1] Implement Markdown report generation in `src/workflows/report_formatter.py` (FR-008: executive summary, detailed findings, citations, metadata)
- [ ] T031 [US1] Implement Windmill workflow script in `src/windmill/daily_research.py` (validate input, run graph, return result fields needed by API)
- [ ] T031a [US1] Configure Windmill job settings to enforce subprocess isolation with 1 CPU / 2GB memory limits per FR-010 (prevent resource exhaustion)
- [ ] T032 [US1] Implement API routes in `src/api/routes/daily_trending_research.py` to match contract (create run, get status, get report)
- [ ] T033 [US1] Wire API router into app in `src/api/app.py` and ensure FastAPI OpenAPI includes `/v1/research/workflows/daily-trending-research/*`
- [ ] T034 [US1] Ensure run result payload returned by Windmill script matches `ReportResponse` in `src/api/schemas/workflow_api.py`

**Checkpoint**: US1 fully functional and testable independently (API → workflow run → report → memory).

---

## Phase 4: User Story 2 — Human Approval for Sensitive Actions (Priority: P2)

**Goal**: When a planned action is `REVERSIBLE_WITH_DELAY` (or `IRREVERSIBLE`), pause via Windmill native approval; on approval resume and execute; on timeout escalate (log + skip action) within 5 minutes ± 10 seconds.

**Independent Test**: Trigger a run configured to include one `PlannedAction` requiring approval; verify status becomes `suspended_approval` quickly, then programmatically approve/reject and verify workflow resumes; verify timeout path skips action and marks escalation.

### Tests for User Story 2 (REQUIRED) ⚠️

- [ ] T035 [P] [US2] Add unit tests for approval handler with mocked `wmill` in `tests/unit/test_windmill_approval_handler.py` (approved/rejected/timed_out paths; timeout=300s)
- [ ] T036 [P] [US2] Add unit tests for action risk gating in `tests/unit/test_planned_action_risk_gating.py` (REVERSIBLE auto, REVERSIBLE_WITH_DELAY/IRREVERSIBLE require approval)
- [ ] T037 [P] [US2] Add integration test skeleton for approval flow in `tests/integration/test_windmill_approval_flow.py` (marked to skip unless WINDMILL_* env vars set)

### Implementation for User Story 2

- [ ] T038 [P] [US2] Implement approval gate helper in `src/windmill/approval_handler.py` using `wmill.suspend()` with timeout (default from `src/core/config.py`)
- [ ] T039 [US2] Integrate approval gating into `src/windmill/daily_research.py` (iterate `planned_actions`, suspend when needed, handle approve/reject/timeout escalation per FR-006/FR-007)
- [ ] T040 [US2] Extend API status mapping in `src/api/routes/daily_trending_research.py` to populate `RunStatusResponse.approval` when Windmill job is suspended
- [ ] T041 [US2] Add programmatic resume client for tests in `tests/fixtures/windmill_client.py` (resume job approved/rejected, query suspended queue)
- [ ] T042 [US2] Update contract test expectations for approval fields in `tests/contract/test_workflow_api_contract.py` (ApprovalStatus schema behavior)

**Checkpoint**: US2 approval gating works and is independently testable (unit tests always; integration tests when Windmill configured).

---

## Phase 5: User Story 3 — Observe Complete Execution Trace (Priority: P3)

**Goal**: View a complete OpenTelemetry trace covering API request → Windmill step → LangGraph root span → per-node spans → agent tool call spans → memory spans; errors captured in span attributes.

**Independent Test**: Run a workflow with OTEL exporter set to `memory` and assert spans exist for each node + memory ops; optionally confirm Jaeger shows the full trace when using real OTLP endpoint.

### Tests for User Story 3 (REQUIRED) ⚠️

- [ ] T043 [P] [US3] Add unit tests for LangGraph tracing decorators in `tests/unit/test_langgraph_tracing.py` (uses in-memory exporter via `src/core/telemetry.py`)
- [ ] T044 [P] [US3] Add integration test ensuring spans emitted on workflow run in `tests/integration/test_daily_research_tracing.py`

### Implementation for User Story 3

- [ ] T045 [US3] Extend unified telemetry utilities in `src/core/telemetry.py` (add `trace_langgraph_execution()` + `trace_langgraph_node()` decorators; no new telemetry module)
- [ ] T046 [P] [US3] Apply `trace_langgraph_node` to LangGraph nodes in `src/workflows/nodes/plan.py`, `src/workflows/nodes/research.py`, `src/workflows/nodes/critique.py`, `src/workflows/nodes/refine.py`, `src/workflows/nodes/finish.py`
- [ ] T047 [US3] Apply `trace_langgraph_execution` to graph runner in `src/workflows/research_graph.py` (set attributes: topic length, iterations, sources_count)
- [ ] T047a [US3] Update Windmill script in `src/windmill/daily_research.py` to accept `traceparent` argument and link LangGraph root span to the API request (Distributed Tracing)
- [ ] T048 [US3] Add API-level tracing spans in `src/api/routes/daily_trending_research.py` (span per endpoint, propagate `client_traceparent` if provided)

**Checkpoint**: US3 observability is complete and independently testable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, hardening, and quality improvements across stories.

- [ ] T049 [P] Add Spec 003 developer notes for required env vars in `specs/003-daily-research-workflow/quickstart.md` (WINDMILL_*, OTEL, Azure AI Foundry)
- [ ] T050 Add “no PII in metadata” guardrails in `src/workflows/nodes/finish.py` (avoid storing emails/names in MemoryManager metadata)
- [ ] T051 [P] Add API smoke test instructions in `README.md` (how to run `python -m src.cli.run_api` + curl examples from `quickstart.md`)
- [ ] T052 [P] Add or update module exports for new models in `src/models/__init__.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**
- **US1 (Phase 3)**: Depends on Foundational
- **US2 (Phase 4)**: Depends on US1 (approval fields integrate into run lifecycle + status shape)
- **US3 (Phase 5)**: Depends on US1 (needs real nodes/graph); can be developed in parallel with US2 once US1 exists
- **Polish (Phase 6)**: Depends on whichever stories are in scope for the release

### User Story Dependencies (Graph)

- **US1 → US2**: US2 extends the run lifecycle with approval suspension/resume and requires status/report surfaces to exist
- **US1 → US3**: US3 instruments the already-built graph nodes + API endpoints

### Within Each User Story

- Tests should be written first and fail before implementation
- Models/config before services/clients
- Graph/node logic before Windmill wrapper before API endpoints

---

## Parallel Execution Examples

### Parallel Example: User Story 1

```bash
# Tests (parallel):
Task: "T020 Add OpenAPI contract test in tests/contract/test_workflow_api_contract.py"
Task: "T021 Add unit tests for report formatting in tests/unit/test_report_formatter.py"
Task: "T022 Add unit tests for iteration cap in tests/unit/test_research_graph_iteration_limit.py"

# Nodes (parallel):
Task: "T024 Implement Plan node in src/workflows/nodes/plan.py"
Task: "T026 Implement Critique node in src/workflows/nodes/critique.py"
Task: "T027 Implement Refine node in src/workflows/nodes/refine.py"
```

### Parallel Example: User Story 2

```bash
# Unit tests + fixtures (parallel):
Task: "T035 Add unit tests in tests/unit/test_windmill_approval_handler.py"
Task: "T041 Add Windmill test client in tests/fixtures/windmill_client.py"

# Implementation (mostly parallel, different files):
Task: "T038 Implement approval gate in src/windmill/approval_handler.py"
Task: "T040 Extend API status mapping in src/api/routes/daily_trending_research.py"
```

### Parallel Example: User Story 3

```bash
# Decorators + node instrumentation (parallel once T045 is in):
Task: "T046 Apply trace_langgraph_node in src/workflows/nodes/*.py"
Task: "T048 Add API spans in src/api/routes/daily_trending_research.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 (tests + implementation)
4. Stop and validate: contract + unit + integration tests; manual API run via `specs/003-daily-research-workflow/quickstart.md`

### Incremental Delivery

1. Add US2 approval gating (suspend/resume/timeout escalation)
2. Add US3 observability (LangGraph node spans + API spans)
3. Polish documentation + guardrails


