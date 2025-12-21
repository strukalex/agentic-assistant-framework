---

description: "Task list template for feature implementation"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are **REQUIRED** to meet the project constitution’s quality gate (**≥ 80% coverage**).
Any exception MUST be explicitly justified and approved via **Article V (Amendment Process)** in
`.specify/memory/constitution.md`.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- **Web app**: `backend/src/`, `frontend/src/`
- **Mobile**: `api/src/`, `ios/src/` or `android/src/`
- Paths shown below assume single project - adjust based on plan.md structure

## Constitution-driven cross-cutting requirements *(mandatory)*

**Source of truth**: `.specify/memory/constitution.md` (v2.0+)

Include tasks to satisfy these non-negotiables (refer to the cited Articles in task descriptions):

- **Article I — Technology stack**: Python 3.11+, pattern-driven orchestration (Windmill/LangGraph/CrewAI/AutoGen per Article I.B), Pydantic AI, PostgreSQL+pgvector with memory abstraction, MCP, Open WebUI, Claude 3.5 Sonnet (default)
- **Article II — Architectural principles (all 7)**:
  - Human-in-the-loop by default (risk-based approvals; irreversible actions never auto-execute)
  - Observable everything (OpenTelemetry traces for decisions/tool calls/approvals)
  - Pluggable orchestration (framework-agnostic agent code; no direct DB driver imports)
  - Isolation & safety boundaries (maturity-triggered per Article II.F)
  - Others as stated in the constitution
- **Article III — Operational standards**:
  - Async I/O for DB/tool calls
  - Alembic migrations for schema changes
  - CI gates for lint/type-check/tests and **coverage ≥ 80%**

<!-- 
  ============================================================================
  IMPORTANT: The tasks below are SAMPLE TASKS for illustration purposes only.
  
  The /speckit.tasks command MUST replace these with actual tasks based on:
  - User stories from spec.md (with their priorities P1, P2, P3...)
  - Feature requirements from plan.md
  - Entities from data-model.md
  - Endpoints from contracts/
  
  Tasks MUST be organized by user story so each story can be:
  - Implemented independently
  - Tested independently
  - Delivered as an MVP increment
  
  DO NOT keep these sample tasks in the generated tasks.md file.
  ============================================================================
-->

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project structure per implementation plan
- [ ] T002 Initialize Python 3.11 project and baseline dependencies (Windmill, LangGraph, Pydantic AI, FastAPI)
- [ ] T003 [P] Configure linting/formatting/type-checking (Ruff, Black, mypy) per constitution
- [ ] T004 [P] Configure pytest + pytest-cov with CI enforcement (`--cov-fail-under=80`)
- [ ] T005 [P] Add OpenTelemetry baseline instrumentation scaffolding (traces for agent runs + tool calls)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

Examples of foundational tasks (adjust based on your project):

- [ ] T006 Setup PostgreSQL + pgvector schema and Alembic migrations
- [ ] T007 [P] Setup API routing and middleware structure (FastAPI)
- [ ] T008 Create base models/entities that all stories depend on
- [ ] T009 Configure error handling + structured logging + tracing
- [ ] T010 Setup MCP client/server integration pattern (no hardcoded tool integrations)
- [ ] T011 Implement human-in-the-loop approval gates for irreversible actions (constitution Article II.C)
- [ ] T012 Setup environment configuration management

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - [Title] (Priority: P1) 🎯 MVP

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 1 (REQUIRED) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T100 [P] [US1] Contract test for [endpoint] in tests/contract/test_[name].py
- [ ] T101 [P] [US1] Integration test for [user journey] in tests/integration/test_[name].py

### Implementation for User Story 1

- [ ] T102 [P] [US1] Create [Entity1] model in src/models/[entity1].py
- [ ] T103 [P] [US1] Create [Entity2] model in src/models/[entity2].py
- [ ] T104 [US1] Implement [Service] in src/services/[service].py (depends on T102, T103)
- [ ] T105 [US1] Implement [endpoint/feature] in src/[location]/[file].py
- [ ] T106 [US1] Add validation and error handling
- [ ] T107 [US1] Add logging + tracing spans for User Story 1 operations (Article II.D)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - [Title] (Priority: P2)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 2 (REQUIRED) ⚠️

- [ ] T200 [P] [US2] Contract test for [endpoint] in tests/contract/test_[name].py
- [ ] T201 [P] [US2] Integration test for [user journey] in tests/integration/test_[name].py

### Implementation for User Story 2

- [ ] T202 [P] [US2] Create [Entity] model in src/models/[entity].py
- [ ] T203 [US2] Implement [Service] in src/services/[service].py
- [ ] T204 [US2] Implement [endpoint/feature] in src/[location]/[file].py
- [ ] T205 [US2] Integrate with User Story 1 components (if needed)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - [Title] (Priority: P3)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 3 (REQUIRED) ⚠️

- [ ] T300 [P] [US3] Contract test for [endpoint] in tests/contract/test_[name].py
- [ ] T301 [P] [US3] Integration test for [user journey] in tests/integration/test_[name].py

### Implementation for User Story 3

- [ ] T302 [P] [US3] Create [Entity] model in src/models/[entity].py
- [ ] T303 [US3] Implement [Service] in src/services/[service].py
- [ ] T304 [US3] Implement [endpoint/feature] in src/[location]/[file].py

**Checkpoint**: All user stories should now be independently functional

---

[Add more user story phases as needed, following the same pattern]

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] TXXX [P] Documentation updates in docs/
- [ ] TXXX Code cleanup and refactoring
- [ ] TXXX Performance optimization across all stories
- [ ] TXXX [P] Additional unit tests to maintain/raise coverage in tests/unit/
- [ ] TXXX Security hardening
- [ ] TXXX Run quickstart.md validation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - May integrate with US1 but should be independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - May integrate with US1/US2 but should be independently testable

### Within Each User Story

- Tests MUST be written and FAIL before implementation (to satisfy the constitution’s coverage gate)
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Contract test for [endpoint] in tests/contract/test_[name].py"
Task: "Integration test for [user journey] in tests/integration/test_[name].py"

# Launch all models for User Story 1 together:
Task: "Create [Entity1] model in src/models/[entity1].py"
Task: "Create [Entity2] model in src/models/[entity2].py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1
   - Developer B: User Story 2
   - Developer C: User Story 3
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
