# Tasks: ResearcherAgent with MCP Tools and Tool Gap Detection

**Input**: Design documents from `/specs/002-researcher-agent-mcp/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md (complete), data-model.md (complete), contracts/ (complete)

**Tests**: Tests are **REQUIRED** to meet the project constitution's quality gate (**≥ 80% coverage**).
Any exception MUST be explicitly justified and approved via **Article V (Amendment Process)** in
`.specify/memory/constitution.md`.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Single project structure (from plan.md):
- Source code: `src/`
- Tests: `tests/`
- MCP servers: `mcp-servers/`

## Constitution-driven cross-cutting requirements *(mandatory)*

**Source of truth**: `.specify/memory/constitution.md` (v2.1)
**Project context**: `.specify/memory/project-context.md` (Phase 1: Core Foundation & Agent Layer)

Include tasks to satisfy these non-negotiables (refer to the cited Articles in task descriptions):

- **Article I — Technology stack**: Python 3.11+, Pydantic AI, PostgreSQL+pgvector with memory abstraction, MCP, DeepSeek 3.2 via Microsoft Azure AI Foundry
- **Article II — Architectural principles (all 7)**:
  - Human-in-the-loop by default (risk-based approvals; irreversible actions never auto-execute)
  - Observable everything (OpenTelemetry traces for decisions/tool calls/approvals)
  - Pluggable orchestration (framework-agnostic agent code)
  - Multi-storage memory abstraction (use MemoryManager interface)
  - Tool gap detection & self-extension
  - Isolation & safety boundaries
  - Vertical-slice delivery
- **Article III — Operational standards**:
  - Async I/O for DB/MCP calls/LLM API calls
  - Alembic migrations for schema changes
  - CI gates for lint/type-check/tests and **coverage ≥ 80%**

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create project directory structure per plan.md: src/{agents,core,mcp_integration,models,cli}/, tests/{unit,integration,contract}/, mcp-servers/time-context/
- [X] T002 Initialize Python 3.11+ project with pyproject.toml using Poetry, add baseline dependencies: pydantic-ai[azure], mcp, asyncpg, sqlmodel, opentelemetry-api, opentelemetry-sdk, opentelemetry-exporter-otlp
- [X] T003 [P] Configure linting/formatting/type-checking tools in pyproject.toml: ruff (linter), black (formatter), mypy (type checker) per Constitution Article III
- [X] T004 [P] Configure pytest with pytest.ini: add pytest, pytest-cov, pytest-asyncio dependencies, set --cov-fail-under=80 per Constitution Article III.A
- [X] T005 [P] Create .env.example file with all required environment variables: AZURE_AI_FOUNDRY_ENDPOINT, AZURE_AI_FOUNDRY_API_KEY, AZURE_DEPLOYMENT_NAME, WEBSEARCH_ENGINE, WEBSEARCH_MAX_RESULTS, WEBSEARCH_TIMEOUT, OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SERVICE_NAME, DATABASE_URL (FR-027, FR-028, FR-029)
- [X] T006 [P] Create docker-compose.yml with PostgreSQL 15 + pgvector extension (port 5432) and Jaeger all-in-one (UI port 16686, OTLP port 4317) per plan.md infrastructure requirements

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 Create RiskLevel enum in src/models/risk_level.py with values: REVERSIBLE, REVERSIBLE_WITH_DELAY, IRREVERSIBLE per data-model.md (FR-015)
- [X] T008 [P] Create ToolCallStatus enum in src/models/agent_response.py with values: SUCCESS, FAILED, TIMEOUT per data-model.md
- [X] T009 [P] Create ToolCallRecord Pydantic model in src/models/agent_response.py with fields: tool_name (str), parameters (dict), result (Optional[Any]), duration_ms (int, ge=0), status (ToolCallStatus) per data-model.md
- [X] T010 Create AgentResponse Pydantic model in src/models/agent_response.py with fields: answer (str, min_length=1), reasoning (str, min_length=1), tool_calls (List[ToolCallRecord]), confidence (confloat ge=0.0, le=1.0) per data-model.md (FR-003)
- [X] T011 [P] Create ToolGapReport Pydantic model in src/models/tool_gap_report.py with fields: missing_tools (List[str], min_items=1), attempted_task (str, min_length=1), existing_tools_checked (List[str]) per data-model.md (FR-013)
- [X] T012 Implement categorize_action_risk(tool_name: str, parameters: dict) -> RiskLevel function in src/core/risk_assessment.py using TOOL_RISK_MAP with parameter inspection for sensitive file paths per research.md RQ-006 (FR-015 to FR-019)
- [X] T013 Implement requires_approval(action: RiskLevel, confidence: float) -> bool function in src/core/risk_assessment.py: return True for IRREVERSIBLE always, True for REVERSIBLE_WITH_DELAY if confidence < 0.85, False for REVERSIBLE per research.md RQ-006 (FR-020 to FR-023)
- [X] T014 Setup OpenTelemetry tracing infrastructure in src/core/telemetry.py: configure TracerProvider, BatchSpanProcessor, OTLPSpanExporter with endpoint from OTEL_EXPORTER_OTLP_ENDPOINT env var, service name from OTEL_SERVICE_NAME env var per research.md RQ-004 (FR-029, FR-032). Note: Uses unified telemetry module per Constitution Article II.H
- [X] T015 Implement @trace_tool_call decorator in src/core/telemetry.py: create span with name "mcp.tool_call.{func_name}", set attributes tool_name, parameters, result_count, handle errors with span.record_exception() per research.md RQ-004 (FR-030). Note: Uses unified telemetry module per Constitution Article II.H
- [X] T016 Implement custom MCP time server in mcp-servers/time-context/server.py: create Python-based MCP server with get_current_time(timezone: str = 'UTC') tool returning dict with timestamp (ISO 8601), timezone, unix_epoch per plan.md structure (FR-008)
- [X] T017 Implement setup_mcp_tools() async function in src/mcp_integration/setup.py: initialize 3 MCP servers using StdioServerParameters (Open-WebSearch via "npx -y @open-websearch/mcp-server", mcp-server-filesystem read-only, custom time server), return ClientSession per research.md RQ-002 (FR-005)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Basic Research Query Execution (Priority: P1) 🎯 MVP

**Goal**: Enable ResearcherAgent to answer simple factual questions using web search, time context, and memory search tools

**Independent Test**: Submit "What is the capital of France?" and verify agent returns AgentResponse with correct answer, reasoning showing web_search tool usage, tool_calls list populated, and confidence > 0.5

### Tests for User Story 1 (REQUIRED) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T100 [P] [US1] Write contract test in tests/contract/test_agent_api_contract.py to validate agent.run() returns AgentResponse schema matching contracts/researcher-agent-api.yaml for simple query "What is the capital of France?"
- [X] T101 [P] [US1] Write integration test in tests/integration/test_mcp_tools.py to verify setup_mcp_tools() successfully initializes all 3 MCP servers (Open-WebSearch, filesystem, time) and list_tools() returns expected tool schemas (FR-005, FR-006, FR-007, FR-008)
- [X] T102 [P] [US1] Write integration test in tests/integration/test_memory_integration.py to verify search_memory and store_memory tools work with MemoryManager dependency injection via RunContext (FR-024, FR-025, FR-026)
- [X] T103 [P] [US1] Write unit test in tests/unit/test_researcher_agent.py to verify ResearcherAgent initialization with DeepSeek 3.2 via AzureModel, result_type=AgentResponse, retries=2 (FR-001, FR-002, FR-003, FR-004, FR-034)

### Implementation for User Story 1

- [X] T104 [US1] Initialize ResearcherAgent in src/agents/researcher.py: configure Pydantic AI Agent with AzureModel(model_name="deepseek-v3", endpoint from AZURE_AI_FOUNDRY_ENDPOINT, api_key from AZURE_AI_FOUNDRY_API_KEY), set result_type=AgentResponse, retries=2, define system prompt listing capabilities per research.md RQ-001 (FR-001, FR-002, FR-003, FR-004)
- [X] T105 [US1] Register search_memory tool in src/agents/researcher.py using @researcher_agent.tool decorator: accept ctx: RunContext[MemoryManager] and query: str, call ctx.deps.semantic_search(query, top_k=5), return List[dict] with content and metadata per research.md RQ-007 (FR-024)
- [X] T106 [US1] Register store_memory tool in src/agents/researcher.py using @researcher_agent.tool decorator: accept ctx: RunContext[MemoryManager], content: str, metadata: dict, call ctx.deps.store_document(content, metadata), return document ID as string per research.md RQ-007 (FR-025)
- [X] T107 [US1] Implement setup_researcher_agent() async function in src/agents/researcher.py: call setup_mcp_tools() to initialize MCP session, configure agent with MemoryManager dependency via RunContext[MemoryManager], return tuple (agent, mcp_session) matching contracts/researcher-agent-api.yaml usage pattern (FR-026, FR-034)
- [X] T108 [US1] Instrument agent.run() calls with OpenTelemetry in src/agents/researcher.py: wrap run() invocation with tracer span "agent_run", set attributes confidence_score, tool_calls_count, task_description, result_type per research.md RQ-004 (FR-031)
- [X] T109 [US1] Apply @trace_tool_call decorator to all MCP tool invocations in src/agents/researcher.py to capture tool_name, parameters, result_count, execution_duration_ms per observability requirements (FR-030)

**Checkpoint**: At this point, User Story 1 should be fully functional - agent can execute basic research queries using web search, time context, and memory tools with full OpenTelemetry tracing

---

## Phase 4: User Story 2 - Tool Gap Detection and Honest Reporting (Priority: P2)

**Goal**: Enable agent to detect when a task requires tools it doesn't have and report capability gaps honestly without hallucinating

**Independent Test**: Submit "Retrieve my stock portfolio performance for Q3 2024" when no financial API tool is available, verify agent returns ToolGapReport with missing_tools=["financial_data_api"], does NOT fabricate data

### Tests for User Story 2 (REQUIRED) ⚠️

- [X] T200 [P] [US2] Write contract test in tests/contract/test_agent_api_contract.py to validate ToolGapDetector.detect_missing_tools() returns ToolGapReport schema matching contracts/researcher-agent-api.yaml when capability gap exists
- [X] T201 [P] [US2] Write unit test in tests/unit/test_tool_gap_detector.py to verify detect_missing_tools() returns ToolGapReport with missing_tools populated when task requires unavailable tool (e.g., financial API) (FR-009, FR-011, FR-012, FR-013)
- [X] T202 [P] [US2] Write unit test in tests/unit/test_tool_gap_detector.py to verify detect_missing_tools() returns None when all required capabilities are available via existing MCP tools (FR-014)
- [X] T203 [P] [US2] Write integration test in tests/integration/test_tool_gap_detection.py to verify end-to-end gap detection: submit task requiring missing tool, verify agent calls ToolGapDetector and returns ToolGapReport without attempting hallucinated execution

### Implementation for User Story 2

- [X] T204 [P] [US2] Implement ToolGapDetector class in src/core/tool_gap_detector.py with __init__(mcp_session: ClientSession) storing session reference per research.md RQ-005 (FR-009)
- [X] T205 [US2] Implement ToolGapDetector.detect_missing_tools(task_description: str) -> Optional[ToolGapReport] method: call mcp_session.list_tools() to get available tools, store in self.available_tools if None per research.md RQ-005 (FR-010)
- [X] T206 [US2] Implement capability extraction in ToolGapDetector.detect_missing_tools() using DeepSeek 3.2 LLM: send prompt to extract required capabilities from task_description as JSON array of capability names per research.md RQ-005 (FR-011)
- [X] T207 [US2] Implement schema matching in ToolGapDetector.detect_missing_tools(): compare extracted required capabilities against available MCP tool names, identify missing tools per research.md RQ-005 (FR-012)
- [X] T208 [US2] Return ToolGapReport in ToolGapDetector.detect_missing_tools() when capability gaps detected: populate missing_tools, attempted_task (copy of task_description), existing_tools_checked (list of available tool names) per research.md RQ-005 (FR-013)
- [X] T209 [US2] Return None in ToolGapDetector.detect_missing_tools() when all required capabilities available in MCP tools (no gaps) per research.md RQ-005 (FR-014)
- [X] T210 [US2] Integrate ToolGapDetector into ResearcherAgent workflow in src/agents/researcher.py: before executing task, call detector.detect_missing_tools(), if ToolGapReport returned, return it to user instead of attempting execution

**Checkpoint**: At this point, User Story 2 should be fully functional - agent detects and reports tool capability gaps honestly, preventing hallucinated execution

---

## Phase 5: User Story 3 - Risk-Based Action Approval Workflow (Priority: P3)

**Goal**: Enforce human-in-the-loop approval for high-risk actions (IRREVERSIBLE) while auto-executing safe actions (REVERSIBLE) based on confidence thresholds per Constitution Article II.C

**Independent Test**: Simulate tool invocations with different risk levels - verify web_search (REVERSIBLE) auto-executes, hypothetical send_email (REVERSIBLE_WITH_DELAY, confidence=0.80) requires approval, hypothetical delete_file (IRREVERSIBLE, confidence=0.95) always requires approval

### Tests for User Story 3 (REQUIRED) ⚠️

- [X] T300 [P] [US3] Write contract test in tests/contract/test_agent_api_contract.py to validate categorize_action_risk() and requires_approval() return correct types per contracts/researcher-agent-api.yaml
- [X] T301 [P] [US3] Write unit test in tests/unit/test_risk_assessment.py to verify categorize_action_risk() correctly classifies known REVERSIBLE tools: web_search, read_file, get_current_time, search_memory (FR-016)
- [X] T302 [P] [US3] Write unit test in tests/unit/test_risk_assessment.py to verify categorize_action_risk() correctly classifies hypothetical REVERSIBLE_WITH_DELAY tools: send_email, create_calendar_event, schedule_task (FR-017)
- [X] T303 [P] [US3] Write unit test in tests/unit/test_risk_assessment.py to verify categorize_action_risk() correctly classifies hypothetical IRREVERSIBLE tools: delete_file, make_purchase, send_money, modify_production (FR-018)
- [X] T304 [P] [US3] Write unit test in tests/unit/test_risk_assessment.py to verify categorize_action_risk() defaults to IRREVERSIBLE for unknown tools (FR-019)
- [X] T305 [P] [US3] Write unit test in tests/unit/test_risk_assessment.py to verify requires_approval() returns True for all IRREVERSIBLE actions regardless of confidence (FR-021)
- [X] T306 [P] [US3] Write unit test in tests/unit/test_risk_assessment.py to verify requires_approval() returns True for REVERSIBLE_WITH_DELAY when confidence < 0.85, False when confidence >= 0.85 (FR-022)
- [X] T307 [P] [US3] Write unit test in tests/unit/test_risk_assessment.py to verify requires_approval() returns False for REVERSIBLE actions enabling auto-execution with logging (FR-023)

### Implementation for User Story 3

- [X] T308 [US3] Integrate risk assessment into ResearcherAgent tool execution pipeline in src/agents/researcher.py: before invoking any MCP tool, call categorize_action_risk(tool_name, parameters) to get RiskLevel
- [X] T309 [US3] Implement approval check in ResearcherAgent tool execution in src/agents/researcher.py: call requires_approval(risk_level, confidence), if True, block execution and request user approval before proceeding
- [X] T310 [US3] Add logging for auto-executed REVERSIBLE actions in src/agents/researcher.py: when requires_approval() returns False, log tool invocation with risk level and confidence before auto-execution
- [X] T311 [US3] Implement parameter inspection for context-dependent risk in src/core/risk_assessment.py categorize_action_risk(): detect sensitive patterns in file paths (e.g., "/etc/shadow", "api_key", "secret", "credentials") and escalate read_file from REVERSIBLE to REVERSIBLE_WITH_DELAY per research.md RQ-006

**Checkpoint**: All user stories should now be independently functional - agent executes basic research (US1), detects tool gaps (US2), and enforces risk-based approval (US3)

---

## Phase 6: User Story 4 - Memory Integration for Knowledge Persistence (Priority: P4)

**Goal**: Enable ResearcherAgent to search for previously stored knowledge in semantic memory layer and store new research findings for future retrieval

**Independent Test**: Store document via store_memory("Project X uses Python 3.11 and FastAPI", metadata={"project": "X"}), later search via search_memory("What tech stack does Project X use?"), verify stored document retrieved and used in response

### Tests for User Story 4 (REQUIRED) ⚠️

- [X] T400 [P] [US4] Write integration test in tests/integration/test_memory_integration.py to verify agent stores research findings via store_memory() after executing web_search and returns document ID (FR-025)
- [X] T401 [P] [US4] Write integration test in tests/integration/test_memory_integration.py to verify agent retrieves past research via search_memory() when user asks related question, includes memory source in reasoning field (FR-024, FR-026)
- [X] T402 [P] [US4] Write unit test in tests/unit/test_researcher_agent.py to verify ResearcherAgent is initialized with MemoryManager as dependency via RunContext[MemoryManager] (FR-026)

### Implementation for User Story 4

- [X] T403 [US4] Enhance agent task execution in src/agents/researcher.py to automatically call search_memory() first for any user query to check for previously stored relevant knowledge before executing expensive web_search
- [X] T404 [US4] Enhance agent response synthesis in src/agents/researcher.py to automatically call store_memory() after synthesizing research findings from web_search, store with metadata including topic, timestamp, and source tools used
- [X] T405 [US4] Update agent reasoning field generation in src/agents/researcher.py to cite memory sources when search_memory() returns relevant past research (e.g., "Based on prior research stored on 2025-12-15...")

**Checkpoint**: At this point, User Story 4 should be fully functional - agent integrates with memory layer for knowledge persistence and retrieval

---

## Phase 7: User Story 5 - OpenTelemetry Observability for All Tool Calls (Priority: P5)

**Goal**: Ensure all ResearcherAgent operations are fully instrumented with OpenTelemetry tracing, visible in Jaeger UI with detailed span attributes

**Independent Test**: Execute research query, access Jaeger UI (localhost:16686), verify trace spans appear with service name "paias", span names matching tool calls, attributes including tool_name, parameters, result_count, confidence_score

### Tests for User Story 5 (REQUIRED) ⚠️

- [X] T500 [P] [US5] Write integration test in tests/integration/test_telemetry.py to verify OpenTelemetry exporter is configured with OTLP endpoint from OTEL_EXPORTER_OTLP_ENDPOINT env var (FR-029, FR-032). Note: Tests unified telemetry module per Constitution Article II.H
- [X] T501 [P] [US5] Write integration test in tests/integration/test_telemetry.py to verify all MCP tool invocations create trace spans with attributes: tool_name, parameters (serialized), result_count, execution_duration_ms (FR-030)
- [X] T502 [P] [US5] Write integration test in tests/integration/test_telemetry.py to verify agent.run() calls create trace spans with attributes: confidence_score, tool_calls_count, task_description, result_type (FR-031)
- [X] T503 [P] [US5] Write unit test in tests/unit/test_telemetry.py to verify @trace_tool_call decorator correctly creates spans and handles errors by setting span status to ERROR with error details

### Implementation for User Story 5

- [X] T504 [US5] Enhance @trace_tool_call decorator in src/core/telemetry.py to capture execution_duration_ms by measuring time before/after tool invocation
- [X] T505 [US5] Add span attributes for error handling in src/core/telemetry.py @trace_tool_call decorator: capture error_type, error_message when tool execution fails or times out (Note: error_type and error_message already captured via span.record_exception(), verified implementation)
- [X] T506 [US5] Verify all agent.run() spans in src/agents/researcher.py include complete set of attributes: confidence_score from result.confidence, tool_calls_count from len(result.tool_calls), task_description from input query
- [X] T507 [US5] Add parent-child span linking in src/agents/researcher.py: ensure all mcp_tool_call spans are children of agent_run span for trace hierarchy visualization in Jaeger

**Checkpoint**: At this point, all user stories are complete with full observability - all operations traced and visible in Jaeger UI

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories, final validations, and documentation

- [X] T600 [P] CLI test tool already exists at src/cli/test_agent.py (moved from specs/002-researcher-agent-mcp/scripts/manual_test_agent.py): accepts query as command-line argument, initializes agent with run_researcher_agent(), executes query, prints AgentResponse or ToolGapReport with formatting, includes risk assessment logging per quickstart.md
- [X] T601 [P] Risk assessment testing integrated into src/cli/test_agent.py: demonstrates risk categorization for all tool invocations (REVERSIBLE, REVERSIBLE_WITH_DELAY, IRREVERSIBLE) with approval workflow logging per quickstart.md step 10 and src/cli/README.md
- [X] T602 [P] Add comprehensive error handling for MCP tool failures in src/mcp_integration/setup.py: catch MCP server initialization errors, return clear error messages indicating which server failed (e.g., "Failed to connect to Open-WebSearch MCP server: npx command not found") per edge cases in spec.md
- [X] T603 [P] Add timeout handling for MCP tool calls in src/agents/researcher.py: configure WEBSEARCH_TIMEOUT from env var, catch timeout exceptions, return AgentResponse with confidence=0.0 and reasoning explaining failure per edge cases in spec.md
- [X] T604 [P] Add malformed data handling for MCP tool responses in src/agents/researcher.py: catch JSON parsing errors and schema validation failures, log with OpenTelemetry, return AgentResponse with confidence=0.0 per edge cases in spec.md
- [X] T605a [P] Write unit test in tests/unit/test_researcher_agent.py to verify agent initialization fails with clear error message when required environment variables are missing (AZURE_AI_FOUNDRY_ENDPOINT, AZURE_AI_FOUNDRY_API_KEY, AZURE_DEPLOYMENT_NAME) per FR-027
- [ ] T606 Validate all test scenarios from quickstart.md work end-to-end: test MCP tool availability (step 5), run test suite (step 6), manual CLI test (step 7), view Jaeger traces (step 8), test tool gap detection (step 9), test risk assessment (step 10)
- [X] T607 Run full test suite: pytest tests/ and verify all tests pass
- [ ] T608 Run linting and type checking: ruff check src/ tests/, black --check src/ tests/, mypy src/ and fix any issues per Constitution Article III
- [ ] T609 [P] Update README.md with quickstart instructions: link to specs/002-researcher-agent-mcp/quickstart.md for setup and usage
- [ ] T610 Verify all Success Criteria from spec.md are met: SC-001 through SC-010 validated through tests and manual verification

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational phase completion - No dependencies on other stories
- **User Story 2 (Phase 4)**: Depends on Foundational phase completion - No dependencies on other stories
- **User Story 3 (Phase 5)**: Depends on Foundational phase completion - Integrates with US1 but independently testable
- **User Story 4 (Phase 6)**: Depends on Foundational phase completion - Enhances US1 but independently testable
- **User Story 5 (Phase 7)**: Depends on Foundational phase completion - Applies to all user stories but independently testable
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories (basic research query execution)
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - No dependencies on other stories (tool gap detection is independent capability)
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Integrates with US1 tool execution but independently testable (risk-based approval workflow)
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - Enhances US1 with memory persistence but independently testable
- **User Story 5 (P5)**: Can start after Foundational (Phase 2) - Applies observability to all operations but independently testable

### Within Each User Story

- Tests MUST be written and FAIL before implementation (to satisfy the constitution's coverage gate)
- Models before services/tools
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- **Setup (Phase 1)**: Tasks T003, T004, T005, T006 can run in parallel
- **Foundational (Phase 2)**: Tasks T008, T009, T011 can run in parallel (different model files)
- **User Story 1 Tests**: Tasks T100, T101, T102, T103 can run in parallel (different test files)
- **User Story 2 Tests**: Tasks T200, T201, T202, T203 can run in parallel (different test files)
- **User Story 2 Implementation**: Task T204 can run in parallel with other tasks once Foundational is complete
- **User Story 3 Tests**: Tasks T301-T307 can run in parallel (all test different aspects of risk_assessment.py)
- **User Story 4 Tests**: Tasks T400, T401, T402 can run in parallel (different test files)
- **User Story 5 Tests**: Tasks T500, T501, T502, T503 can run in parallel (different test files)
- **Polish**: Tasks T600, T601, T602, T603, T604, T605, T609 can run in parallel (different files)
- **After Foundational completes**: All user stories (US1-US5) can start in parallel if team capacity allows

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task T100: "Contract test for agent.run() in tests/contract/test_agent_api_contract.py"
Task T101: "Integration test for MCP tools setup in tests/integration/test_mcp_tools.py"
Task T102: "Integration test for memory integration in tests/integration/test_memory_integration.py"
Task T103: "Unit test for ResearcherAgent initialization in tests/unit/test_researcher_agent.py"

# After tests written and failing, launch implementation tasks sequentially:
Task T104: "Initialize ResearcherAgent in src/agents/researcher.py" (FIRST - creates base agent)
Task T105: "Register search_memory tool in src/agents/researcher.py" (depends on T104)
Task T106: "Register store_memory tool in src/agents/researcher.py" (depends on T104)
Task T107: "Implement setup_researcher_agent() in src/agents/researcher.py" (depends on T104-T106)
Task T108: "Instrument agent.run() with OpenTelemetry in src/agents/researcher.py" (depends on T104)
Task T109: "Apply @trace_tool_call decorator to MCP tool invocations in src/agents/researcher.py" (depends on T104)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Basic Research Query Execution)
4. **STOP and VALIDATE**: Test User Story 1 independently with manual CLI tests and Jaeger traces
5. Deploy/demo if ready

This delivers a working ResearcherAgent that can answer basic research questions using web search, time context, and memory tools - validating the core Pydantic AI + MCP + DeepSeek 3.2 integration.

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo (adds tool gap detection)
4. Add User Story 3 → Test independently → Deploy/Demo (adds risk-based approval)
5. Add User Story 4 → Test independently → Deploy/Demo (adds memory persistence)
6. Add User Story 5 → Test independently → Deploy/Demo (adds full observability)
7. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Basic Research Query Execution)
   - Developer B: User Story 2 (Tool Gap Detection)
   - Developer C: User Story 3 (Risk-Based Action Approval)
3. User Stories 4 and 5 can be added incrementally as enhancements
4. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies within the task group
- [Story] label maps task to specific user story for traceability (US1, US2, US3, US4, US5)
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD approach)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All tasks reference specific file paths for clarity
- Constitution compliance built into task descriptions (Article references included)
- Coverage requirement (≥ 80%) enforced through pytest configuration
- Tests are REQUIRED (not optional) per Constitution Article III.A

---

## Total Task Count: 68 tasks

### Breakdown by Phase:
- **Phase 1 (Setup)**: 6 tasks
- **Phase 2 (Foundational)**: 11 tasks
- **Phase 3 (User Story 1)**: 10 tasks (4 tests + 6 implementation)
- **Phase 4 (User Story 2)**: 11 tasks (4 tests + 7 implementation)
- **Phase 5 (User Story 3)**: 12 tasks (8 tests + 4 implementation)
- **Phase 6 (User Story 4)**: 6 tasks (3 tests + 3 implementation)
- **Phase 7 (User Story 5)**: 8 tasks (4 tests + 4 implementation)
- **Phase 8 (Polish)**: 11 tasks

### Breakdown by User Story:
- **User Story 1 (P1)**: 10 tasks - Basic Research Query Execution
- **User Story 2 (P2)**: 11 tasks - Tool Gap Detection
- **User Story 3 (P3)**: 12 tasks - Risk-Based Action Approval
- **User Story 4 (P4)**: 6 tasks - Memory Integration
- **User Story 5 (P5)**: 8 tasks - OpenTelemetry Observability

### Parallel Opportunities Identified:
- Setup phase: 4 parallel tasks
- Foundational phase: 3 parallel tasks
- User Story 1 tests: 4 parallel tasks
- User Story 2 tests: 4 parallel tasks
- User Story 2 implementation: 1 parallel task
- User Story 3 tests: 7 parallel tasks
- User Story 4 tests: 3 parallel tasks
- User Story 5 tests: 4 parallel tasks
- Polish phase: 7 parallel tasks
- **All 5 user stories can proceed in parallel after Foundational phase completes**

### Suggested MVP Scope:
**Phase 1 (Setup) + Phase 2 (Foundational) + Phase 3 (User Story 1)** = 27 tasks

This delivers a working ResearcherAgent that validates the core architecture:
- ✅ Pydantic AI + Azure AI Foundry (DeepSeek 3.2) integration
- ✅ MCP tool integration (web search, filesystem, time context)
- ✅ Memory layer integration (search + store)
- ✅ OpenTelemetry observability
- ✅ ≥ 80% test coverage
- ✅ Constitution compliance (all Articles I-III)

### Format Validation:
✅ ALL tasks follow the checklist format:
- ✅ Checkbox `- [ ]` prefix
- ✅ Sequential Task IDs (T001, T002, ...)
- ✅ [P] markers for parallelizable tasks
- ✅ [Story] labels for user story tasks (US1-US5)
- ✅ Exact file paths in descriptions
- ✅ Clear action verbs (Create, Implement, Write, Verify, etc.)
