# Feature Specification: DailyTrendingResearch Workflow

**Feature Branch**: `003-daily-research-workflow`
**Created**: 2025-12-24
**Status**: Draft
**Input**: User description: "Build the DailyTrendingResearch Workflow (Windmill + LangGraph) for Phase 1"

## Constitution Constraints *(mandatory)*

**Source of truth**: `.specify/memory/constitution.md` (v2.3)
**Project context**: `.specify/memory/project-context.md` (Phase 1 — Foundation / Vertical Slice)

This feature MUST comply with the constitution's non-negotiables. If a requirement conflicts with any item below, it MUST be escalated via **Article V (Amendment Process)**.

- **Technology stack (Article I)**:
  - **Python 3.11+**
  - **Orchestration**: Windmill for DAG execution (primary), LangGraph for cyclical reasoning loops (embedded in Windmill steps) per Article I.B
  - **Agents**: Pydantic AI (atomic agent unit) — uses existing ResearcherAgent
  - **Memory**: PostgreSQL 15+ + pgvector (via MemoryManager abstraction layer)
  - **Tools**: MCP-only integrations (no hardcoded tool clients)
  - **Default model**: DeepSeek 3.2 via Microsoft Azure AI Foundry (model-agnostic agents via Pydantic AI)
- **Architectural principles (Article II)**: All 9 principles apply:
  - Vertical-slice delivery (II.A)
  - Pluggable orchestration (II.B)
  - Human-in-the-loop by default (II.C) — REVERSIBLE_WITH_DELAY actions require approval with 5-minute timeout
  - Observable everything (II.D)
  - Multi-storage abstraction (II.E)
  - Isolation & safety boundaries (II.F) — subprocess isolation for agent execution
  - Tool gap detection (II.G)
  - Unified telemetry (II.H) — uses src/core/telemetry.py
  - Shared LLM utilities (II.I) — uses src/core/llm.py
- **Quality gates (Article III)**: Testing is required; CI enforces **>= 80% coverage**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Execute Deep Research on a Topic (Priority: P1)

A user submits a research topic and receives a comprehensive, iteratively refined research report with cited sources. This is the core value proposition of the workflow — transforming a simple topic query into deep, multi-source research output.

**Why this priority**: This is the flagship capability for Phase 1. It demonstrates the complete vertical slice: user input → orchestration → cyclical reasoning → memory storage → formatted output.

**Independent Test**: Can be fully tested by submitting a topic (e.g., "AI governance trends 2025") and verifying a markdown report is generated with at least 3 sources, stored in memory, and returned to the user.

**Acceptance Scenarios**:

1. **Given** a valid topic and user_id, **When** the user triggers the workflow, **Then** the system validates inputs, executes the research loop, and returns a markdown report within 10 minutes.
2. **Given** the research loop produces findings, **When** critique identifies gaps, **Then** the system refines the answer up to 5 iterations before finalizing.
3. **Given** the report is generated, **When** storage is requested, **Then** the system persists the report via MemoryManager with topic, sources, and user_id as metadata.

---

### User Story 2 - Human Approval for Sensitive Actions (Priority: P2)

When the research workflow needs to perform REVERSIBLE_WITH_DELAY actions (e.g., sending a summary email, posting to an external system), the system pauses and requests human approval before proceeding.

**Why this priority**: Implements the Human-in-the-Loop principle (Article II.C) which is a constitutional requirement. Critical for building user trust and preventing unintended side effects.

**Independent Test**: Can be tested by configuring the workflow to trigger an approval gate, verifying the workflow pauses, and confirming it resumes or escalates correctly based on human response.

**Acceptance Scenarios**:

1. **Given** the workflow reaches an action requiring approval, **When** the approval gate activates, **Then** the system pauses execution and sends an approval request via Windmill's native system.
2. **Given** an approval request is pending, **When** the user approves within 5 minutes, **Then** the workflow resumes and completes the action.
3. **Given** an approval request is pending, **When** 5 minutes elapse without response, **Then** the system escalates (logs timeout, skips action, and continues or notifies admin).

---

### User Story 3 - Observe Complete Execution Trace (Priority: P3)

An operator or developer can view the complete execution trace of a research workflow run, from initial request through each LangGraph node to final output, enabling debugging and performance analysis.

**Why this priority**: Implements Observable Everything (Article II.D). Essential for debugging, performance optimization, and demonstrating production readiness.

**Independent Test**: Can be tested by executing a workflow and verifying OpenTelemetry traces appear in Jaeger with spans for: Windmill step entry, each LangGraph node (Plan, Research, Critique, Refine, Finish), agent tool calls, and memory operations.

**Acceptance Scenarios**:

1. **Given** a workflow execution completes, **When** an operator queries Jaeger, **Then** they see a trace with spans for each workflow step and LangGraph node.
2. **Given** any step fails, **When** the operator views traces, **Then** error details, exception messages, and stack traces are captured in span attributes.
3. **Given** agents make tool calls, **When** traces are inspected, **Then** each MCP tool invocation has its own child span with input/output recorded.

---

### Edge Cases

- **What happens when input validation fails?** The workflow returns an error response immediately without executing the research loop, logging the validation failure.
- **What happens when the LLM returns empty or malformed content?** The critique step detects insufficient quality, triggers a refine iteration, and if max iterations reached, returns a partial report with a quality warning.
- **What happens when MemoryManager is unavailable?** The workflow logs the storage failure, returns the report to the user (best effort), and flags the run as requiring manual storage reconciliation.
- **What happens when ResearcherAgent cannot find sources?** The critique step identifies missing sources, refine attempts alternate search strategies, and after max iterations, returns available findings with "limited sources" disclaimer.
- **What happens when approval times out?** Per Article II.C, the action is skipped with a logged escalation; workflow continues with remaining non-approval-blocked steps.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST validate `topic` (non-empty string, max 500 characters) and `user_id` (valid UUID) before initiating research.
- **FR-002**: System MUST execute LangGraph as an embedded library within Windmill workflow steps (not as a separate microservice).
- **FR-003**: System MUST implement a cyclical research graph with nodes: Plan, Research, Critique, Refine, and Finish.
- **FR-004**: System MUST track state across iterations including: topic, plan, sources (list), critique, iteration_count, and refined_answer.
- **FR-005**: System MUST limit research iterations to a maximum of 5 before forcing transition to Finish.
- **FR-006**: System MUST pause workflow execution for REVERSIBLE_WITH_DELAY actions and request human approval via Windmill's native approval system.
- **FR-007**: System MUST timeout approval requests after 5 minutes and escalate (log, skip action, notify).
- **FR-008**: System MUST format final research findings as a Markdown report with: executive summary, detailed findings, source citations, and metadata.
- **FR-009**: System MUST store the final report via MemoryManager with metadata: topic, user_id, sources, iteration_count, timestamp.
- **FR-010**: System MUST execute agent code in subprocess isolation with resource limits (1 CPU core, 2GB memory).
- **FR-011**: System MUST emit OpenTelemetry spans for: workflow start/end, each LangGraph node entry/exit, agent tool calls, and memory operations.
- **FR-012**: System MUST integrate ResearcherAgent from the Agent & Tooling Layer (Spec 002) for executing research tasks.
- **FR-013**: System MUST use MemoryManager from the Memory Layer (Spec 001) for context retrieval and storage.
- **FR-014**: System MUST use shared LLM utilities (src/core/llm.py) for model instantiation per Article II.I.
- **FR-015**: System MUST use unified telemetry module (src/core/telemetry.py) for all tracing per Article II.H.

### Key Entities

- **ResearchState**: Represents the state machine for the LangGraph research loop. Contains topic, plan, sources (list of source objects), critique, iteration_count, refined_answer, and status.
- **ResearchReport**: The final output artifact. Contains executive_summary, detailed_findings, sources (with citations), metadata (topic, user_id, iterations, timestamp), and quality_indicators.
- **ApprovalRequest**: Represents a pending human approval. Contains action_type, action_description, requester_id, timeout_at, and status (pending/approved/rejected/escalated).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users receive a research report within 10 minutes of submitting a valid topic (95th percentile).
- **SC-002**: Reports contain findings from at least 3 distinct sources for 80% of successful research runs.
- **SC-003**: Human approval gates pause workflow within 2 seconds of reaching the approval step.
- **SC-004**: 100% of workflow executions have complete OpenTelemetry traces viewable in the observability system.
- **SC-005**: Approval timeout escalation occurs reliably at the 5-minute mark (tolerance: +/- 10 seconds).
- **SC-006**: System handles 10 concurrent research workflows without degradation (queue/execute pattern acceptable).
- **SC-007**: Reports are successfully stored via MemoryManager for 99% of completed research runs.
- **SC-008**: Research loop terminates within 5 iterations for 100% of runs (hard limit enforced).

## Assumptions

- **A-001**: ResearcherAgent from Spec 002 is implemented and available for import, with functional MCP tool integrations.
- **A-002**: MemoryManager from Spec 001 is implemented and available, with async PostgreSQL + pgvector support.
- **A-003**: Windmill is deployed and accessible, with workflow execution and approval system capabilities.
- **A-004**: OpenTelemetry collector (Jaeger) is running and accessible for trace ingestion.
- **A-005**: LangGraph library is compatible with embedded execution within Windmill Python workers.
- **A-006**: Approval escalation action is logging + skipping the blocked action (not blocking the entire workflow).
- **A-007**: Resource limits (1 CPU, 2GB memory) are configured at the Windmill worker level via wmill.yaml.
