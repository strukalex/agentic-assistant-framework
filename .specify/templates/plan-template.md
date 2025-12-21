# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.11+ *(non-negotiable; see Constitution Article I.A)*  
**Primary Dependencies**: Windmill + LangGraph + Pydantic AI *(Article I.B–I.C)*; FastAPI + Pydantic *(Article I.H)*  
**Storage**: PostgreSQL 15+ + pgvector *(Article I.D)*  
**Tool Integration**: Model Context Protocol (MCP) *(Article I.E; no hardcoded integrations)*  
**UI Layer**: Open WebUI *(Article I.F)*  
**Primary LLM**: Claude 3.5 Sonnet *(Article I.G)*  
**Testing**: pytest + pytest-cov; **minimum 80% coverage** *(Article III.A)*  
**Target Platform**: Linux server (baseline)  
**Project Type**: Web/service backend with chat UI integration *(Open WebUI + API; see Constitution Article I.F)*  
**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]  
**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]  
**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before research begins. Re-check after design phase.*

**Source of truth**: `.specify/memory/constitution.md` (v2.0+)

### Constitutional Compliance Checklist (MUST)

- [ ] **Article I — Non-Negotiable Technology Stack**: Implementation uses the approved stack:
  - [ ] **Python 3.11+**
  - [ ] **Orchestration**: Pattern-driven selection (Article I.B)—Windmill for DAG/linear workflows, LangGraph for cyclical reasoning, CrewAI for role-based teams, AutoGen for agent negotiation
  - [ ] **Agents**: Pydantic AI as the atomic agent unit (orchestration remains Windmill/LangGraph)
  - [ ] **Memory**: PostgreSQL + pgvector (PostgreSQL is source of truth; memory abstraction layer required)
  - [ ] **Tools**: MCP-only tool discovery/execution (no hardcoded tool clients)
  - [ ] **UI**: Open WebUI for chat interaction
  - [ ] **Primary model**: Claude 3.5 Sonnet (agent-level model-agnostic via Pydantic AI)

- [ ] **Article II — Architectural Principles (all 7)**: Plan explicitly respects:
  - [ ] Vertical-slice delivery (end-to-end system deliverable)
  - [ ] Pluggable orchestration (framework-agnostic agent code)
  - [ ] Human-in-the-loop by default (risk-based approvals; irreversible actions never auto-execute)
  - [ ] Observable everything (trace tool calls, decisions, approvals, costs)
  - [ ] Multi-storage memory abstraction (no direct DB driver imports in agent code)
  - [ ] Isolation & safety boundaries (maturity-triggered; async-compatible)
  - [ ] Tool gap detection & self-extension (maturity-triggered per Appendix C)

- [ ] **Article III — Operational Standards**:
  - [ ] Tests + CI enforce **≥ 80% coverage** (no "tests optional" plans)
  - [ ] Async I/O for DB, MCP calls, external APIs (no blocking in orchestration layer)
  - [ ] OpenTelemetry instrumentation for agent reasoning + tool calls + approvals

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
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
