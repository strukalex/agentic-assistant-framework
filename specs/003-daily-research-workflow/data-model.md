# Data Model: DailyTrendingResearch Workflow

This document defines the core entities for Spec 003 (“DailyTrendingResearch Workflow”) and their validation rules, relationships, and lifecycle/state transitions.

## Overview

The workflow is orchestrated by **Windmill** with an embedded **LangGraph** cyclical reasoning loop (Plan → Research → Critique → Refine → Finish). The data model focuses on:

- **In-graph state** (`ResearchState`) used by LangGraph nodes
- **Output artifact** (`ResearchReport`) persisted via `MemoryManager` (Spec 001)
- **Human-in-the-loop** gating (`ApprovalRequest`) surfaced by Windmill suspend/resume
- **Source citations** (`SourceReference`) accumulated across research iterations

## Entities

### 1) `SourceReference`

Represents a single source/citation captured during research (typically from MCP web search tool results).

- **Fields**
  - **title**: string, required
  - **url**: string (URL), required
  - **snippet**: string, required, max length 1000
  - **retrieved_at**: datetime (UTC), required (default now)

- **Validation rules**
  - `snippet` MUST be truncated to ≤ 1000 chars before persistence in state/report.
  - `url` SHOULD be a valid absolute URL.

### 2) `PlannedAction` (workflow-internal)

Represents a candidate action the workflow may take after research (e.g., send a summary email). This is the bridge to Windmill approvals.

- **Fields**
  - **action_type**: string, required (e.g., `"send_email"`)
  - **action_description**: string, required
  - **parameters**: object, required (action-specific payload)
  - **risk_level**: enum, required
    - `REVERSIBLE`
    - `REVERSIBLE_WITH_DELAY`
    - `IRREVERSIBLE`

- **Validation rules**
  - Any `REVERSIBLE_WITH_DELAY` action MUST require approval before execution (FR-006).
  - Any `IRREVERSIBLE` action MUST require approval (Constitution Article II.C).

### 3) `ResearchState` (LangGraph state)

Represents the full state machine context passed between LangGraph nodes.

- **Fields**
  - **topic**: string, required, min length 1, max length 500 (FR-001)
  - **user_id**: UUID (string), required (FR-001)
  - **plan**: string, optional
  - **sources**: array of `SourceReference`, default empty
  - **critique**: string, optional
  - **refined_answer**: string, optional
  - **iteration_count**: int, required, default 0, ≥ 0
  - **max_iterations**: int, required, default 5 (FR-005)
  - **status**: enum, required
    - `planning`
    - `researching`
    - `critiquing`
    - `refining`
    - `finished`
  - **quality_score**: float, required, default 0.0, range 0.0–1.0
  - **quality_threshold**: float, required, default 0.8, range 0.0–1.0
  - **planned_actions**: array of `PlannedAction`, default empty

- **Validation rules**
  - `iteration_count` MUST never exceed `max_iterations` (hard stop at 5 per FR-005).
  - `max_iterations` MUST be capped at 5 (even if an override is provided for tests/config).
  - `topic` MUST be validated before graph execution (FR-001).

- **State transitions (high-level)**
  - `planning` → `researching` (Plan node)
  - `researching` → `critiquing` (Research node)
  - `critiquing` → `refining` (Critique node decides “needs improvement”)
  - `refining` → `researching` (Refine node loops back)
  - `critiquing` → `finished` (quality threshold met OR max iterations reached)

### 4) `ResearchReport` (final artifact)

Represents the final formatted output returned to the caller and persisted to memory.

- **Fields**
  - **topic**: string, required
  - **user_id**: UUID (string), required
  - **executive_summary**: string, required
  - **detailed_findings**: string, required
  - **sources**: array of `SourceReference`, required
  - **iterations**: int, required
  - **generated_at**: datetime (UTC), required
  - **quality_indicators**: object, optional
    - **quality_score**: float (0.0–1.0)
    - **warnings**: array of strings
    - **limited_sources**: boolean

- **Persistence mapping (MemoryManager)**
  - **content**: Markdown report text (FR-008)
  - **metadata** (JSONB):
    - `type`: `"research_report"`
    - `topic`: topic
    - `user_id`: user_id
    - `sources`: normalized list of `{title,url}` (avoid large snippets in metadata)
    - `iteration_count`: iterations
    - `timestamp`: generated_at ISO string

### 5) `ApprovalRequest` (Windmill approval gate)

Represents a pending human approval created when the workflow suspends for a risky action.

- **Fields**
  - **action_type**: string, required
  - **action_description**: string, required
  - **requester_id**: UUID/string, optional (system or user)
  - **requested_at**: datetime (UTC), required
  - **timeout_at**: datetime (UTC), required (requested_at + 5 minutes)
  - **status**: enum, required
    - `pending`
    - `approved`
    - `rejected`
    - `escalated` (timeout)
  - **decision_metadata**: object, optional
    - `approved_by` / `rejected_by`
    - `comment`
    - `duration_seconds`
    - `reason` (e.g., `approval_timeout`)

- **Validation rules**
  - Timeout MUST be **5 minutes ± 10 seconds** (FR-007, SC-005).
  - On timeout, the decision MUST escalate to `escalated` and the action MUST be skipped/logged (FR-007).

## Relationships

- **ResearchState → ResearchReport**: 1-to-1 derivation at Finish step.
- **ResearchState.sources → ResearchReport.sources**: sources are accumulated during iterations and included in final report.
- **PlannedAction → ApprovalRequest**: any `PlannedAction` with `risk_level ∈ {REVERSIBLE_WITH_DELAY, IRREVERSIBLE}` maps to an `ApprovalRequest` in Windmill.

## Notes on Privacy / PII

- `user_id` is a UUID; do not store emails, names, or other PII in report metadata.
- If a future `send_email` action is implemented, email addresses MUST NOT be stored in memory unless encrypted (Constitution Article III.F).


