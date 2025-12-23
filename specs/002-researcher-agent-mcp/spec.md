# Feature Specification: ResearcherAgent with MCP Tools and Tool Gap Detection

**Feature Branch**: `002-researcher-agent-mcp`
**Created**: 2025-12-22
**Status**: Draft
**Input**: User description: "Build the ResearcherAgent with MCP Tools and Tool Gap Detection for the PAIAS Phase 1 Vertical Slice"

## Constitution Constraints *(mandatory)*

**Source of truth**: `.specify/memory/constitution.md` (v2.1)
**Project context**: `.specify/memory/project-context.md` (Phase 1: Core Foundation & Agent Layer - 002-agent-layer)

This feature MUST comply with the constitution's non-negotiables. If a requirement
conflicts with any item below, it MUST be escalated via **Article V (Amendment Process)**.

- **Technology stack (Article I)**:
  - **Python 3.11+** with asyncio (Article I.A)
  - **Orchestration**: Pattern-driven selection (Article I.B)—Windmill for DAG/linear workflows, LangGraph for cyclical reasoning, CrewAI for role-based teams, AutoGen for agent negotiation
  - **Agents**: Pydantic AI (atomic agent unit) (Article I.C)
  - **Memory**: PostgreSQL 15+ + pgvector (PostgreSQL is source of truth; memory abstraction layer required)
  - **Tools**: MCP-only integrations (no hardcoded tool clients) (Article I.E)
  - **UI**: Streamlit for Phase 1-2 (proof-of-concept); React/Next.js OR LibreChat for Phase 3+ (decision pending Phase 2 evaluation) *(Article I.F)*
  - **Default model**: DeepSeek 3.2 via Microsoft Azure AI Foundry (model-agnostic agents via Pydantic AI) (Article I.G)
- **Architectural principles (Article II)**: All 7 principles apply (vertical-slice, pluggable orchestration, human-in-the-loop, observable everything, multi-storage abstraction, isolation & safety boundaries, tool gap detection).
- **Quality gates (Article III)**: Testing is required; CI enforces **≥ 80% coverage**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Basic Research Query Execution (Priority: P1)

A user submits a simple factual research question that the ResearcherAgent can answer using available tools (web search, time context, or memory search).

**Why this priority**: This is the foundational capability of the ResearcherAgent. Without this working, the agent provides no value. It validates the core integration between Pydantic AI, Azure AI Foundry (DeepSeek 3.2), and MCP tools.

**Independent Test**: Can be fully tested by submitting "What is the capital of France?" and verifying the agent returns a structured response with correct answer, reasoning, tool calls made (web_search), and confidence score above 0.5.

**Acceptance Scenarios**:

1. **Given** the ResearcherAgent is initialized with DeepSeek 3.2 and all 3 MCP tools (web search, filesystem, time) are connected, **When** the user submits "What is the capital of France?", **Then** the agent executes the web_search tool, returns a structured AgentResponse with answer="Paris", reasoning explaining tool choice, tool_calls list containing web_search details, and confidence > 0.5
2. **Given** the ResearcherAgent is initialized, **When** the user submits "What time is it in UTC?", **Then** the agent executes the get_current_time tool with timezone='UTC' and returns an AgentResponse with the current UTC timestamp
3. **Given** the ResearcherAgent has previously stored knowledge about "project deadline: March 15, 2025" in memory, **When** the user asks "When is the project deadline?", **Then** the agent searches memory, retrieves the stored document, and returns the answer with reasoning indicating memory was searched

---

### User Story 2 - Tool Gap Detection and Honest Reporting (Priority: P2)

A user requests a task that requires tools the ResearcherAgent doesn't have access to (e.g., financial API, email sending, database modification). The agent must detect the capability gap and report it honestly without hallucinating.

**Why this priority**: This validates Article II.G (Tool Gap Detection) from the Constitution, which prevents the agent from making false claims about its capabilities. Essential for trust and reliability.

**Independent Test**: Can be fully tested by submitting "Retrieve my stock portfolio performance for Q3 2024" when no financial API tool is available. Verifies the agent returns a ToolGapReport instead of hallucinating data or claiming to have performed the action.

**Acceptance Scenarios**:

1. **Given** the ResearcherAgent has only web_search, read_file, get_current_time, and memory tools available, **When** the user requests "Retrieve my stock portfolio performance for Q3 2024", **Then** the ToolGapDetector identifies the missing financial API capability, returns a ToolGapReport with missing_tools=["financial_data_api"], attempted_task describing the request, and existing_tools_checked list showing what was available
2. **Given** the agent detects a tool gap, **When** reporting the gap to the user, **Then** the agent provides clear guidance on what capability is missing, what tools were checked, and does NOT fabricate data or claim to have completed the task
3. **Given** the agent is asked to "Delete all customer records from the production database", **When** the agent checks available tools, **Then** it detects the missing database modification capability and returns a ToolGapReport, preventing hallucinated execution

---

### User Story 3 - Risk-Based Action Approval Workflow (Priority: P3)

The system categorizes tool actions by risk level (REVERSIBLE, REVERSIBLE_WITH_DELAY, IRREVERSIBLE) and enforces human-in-the-loop approval for high-risk actions, while auto-executing safe actions based on confidence thresholds.

**Why this priority**: This implements Article II.C (Human-in-the-Loop for Irreversible Actions) from the Constitution. It ensures safety boundaries are enforced before executing actions with consequences.

**Independent Test**: Can be tested independently by simulating tool invocations with different risk levels. Verify web_search (REVERSIBLE) auto-executes, hypothetical send_email (REVERSIBLE_WITH_DELAY) requires approval if confidence < 0.85, and hypothetical delete_file (IRREVERSIBLE) always requires approval regardless of confidence.

**Acceptance Scenarios**:

1. **Given** the agent wants to execute web_search with confidence=0.7, **When** categorize_action_risk("web_search", params) is called, **Then** it returns RiskLevel.REVERSIBLE and requires_approval(REVERSIBLE, 0.7) returns False, allowing auto-execution with logging
2. **Given** the agent wants to execute a hypothetical send_email tool with confidence=0.80, **When** categorize_action_risk("send_email", params) is called, **Then** it returns RiskLevel.REVERSIBLE_WITH_DELAY and requires_approval(REVERSIBLE_WITH_DELAY, 0.80) returns True (because confidence < 0.85), blocking execution until user approval
3. **Given** the agent wants to execute a hypothetical delete_file tool with confidence=0.95, **When** categorize_action_risk("delete_file", params) is called, **Then** it returns RiskLevel.IRREVERSIBLE and requires_approval(IRREVERSIBLE, 0.95) returns True (always requires approval), blocking execution until user explicitly approves
4. **Given** an unknown tool is invoked, **When** categorize_action_risk("unknown_tool", params) is called, **Then** it defaults to RiskLevel.IRREVERSIBLE (safest assumption) and requires approval

---

### User Story 4 - Memory Integration for Knowledge Persistence (Priority: P4)

The ResearcherAgent can search for previously stored knowledge in the semantic memory layer (from Spec 1: Core Foundation & Memory Layer) and store new research findings for future retrieval.

**Why this priority**: This integrates the agent with the memory layer established in Spec 1, enabling knowledge accumulation over time. Validates Article I.D (Memory abstraction layer) and semantic search capabilities.

**Independent Test**: Can be tested independently by storing a document via store_memory("Project X uses Python 3.11 and FastAPI", metadata={"project": "X"}), then later searching via search_memory("What tech stack does Project X use?") and verifying the stored document is retrieved and used in the response.

**Acceptance Scenarios**:

1. **Given** the ResearcherAgent is connected to MemoryManager via RunContext dependency injection, **When** the agent receives a task that generates new knowledge (e.g., "Research the latest Python async best practices"), **Then** the agent executes web_search, synthesizes findings, and calls store_memory(content=summary, metadata={"topic": "python_async", "timestamp": "..."}) to persist the knowledge
2. **Given** the agent has previously stored research findings about "Python async best practices", **When** a user later asks "What are best practices for Python async code?", **Then** the agent calls search_memory(query="python async best practices", top_k=5) first, retrieves the stored document, and includes it in the response reasoning
3. **Given** the semantic search returns relevant past research, **When** the agent constructs its response, **Then** it cites the memory source in the reasoning field (e.g., "Based on prior research stored on 2025-12-15...")

---

### User Story 5 - OpenTelemetry Observability for All Tool Calls (Priority: P5)

All ResearcherAgent operations, including MCP tool invocations and agent.run() calls, are instrumented with OpenTelemetry tracing. Traces appear in Jaeger UI with detailed span attributes.

**Why this priority**: This implements Article II.D (Observable Everything) from the Constitution. Essential for debugging, performance monitoring, and understanding agent behavior in production.

**Independent Test**: Can be tested independently by executing a research query, then accessing Jaeger UI (localhost:16686) and verifying trace spans appear with service name "paias-agent-layer", span names matching tool calls (e.g., "mcp_tool_call:web_search", "agent_run"), and attributes including tool_name, parameters, result_count, and confidence_score.

**Acceptance Scenarios**:

1. **Given** OpenTelemetry is configured with OTLP exporter pointing to localhost:4317, **When** the agent executes a web_search tool call, **Then** a trace span appears in Jaeger UI with span_name="mcp_tool_call:web_search", attributes={tool_name: "web_search", parameters: "{query: '...', max_results: 10}", result_count: 10}, and links to parent agent_run span
2. **Given** the agent executes agent.run() to process a user query, **When** the run completes, **Then** a trace span appears with span_name="agent_run", attributes={confidence_score: 0.85, tool_calls_count: 2}, and child spans for each tool invocation
3. **Given** an error occurs during tool execution (e.g., web search timeout), **When** the error is caught, **Then** the trace span is marked with error status and includes error details in span attributes (error_type, error_message)

---

### Edge Cases

- **What happens when all 3 MCP tools fail to initialize?** The agent initialization should fail gracefully with a clear error message indicating which MCP servers couldn't connect (e.g., "Failed to connect to Open-WebSearch MCP server: npx command not found"). System should not start in a degraded state.

- **How does the system handle an MCP tool returning malformed data?** The agent should catch JSON parsing errors or schema validation failures, log the error with OpenTelemetry tracing, and return an AgentResponse with confidence=0.0 and reasoning explaining the tool failure. Should not crash or hallucinate.

- **What if the user asks the same question twice in a row?** The agent should check memory first (search_memory) to see if the answer was recently stored. If found and still relevant (timestamp within reasonable window), return from memory without re-executing expensive web_search.

- **How does risk categorization handle tools with context-dependent risk?** Example: read_file is REVERSIBLE for most files, but reading /etc/shadow or API keys could be sensitive. The risk_assessment module should have a parameter inspection mechanism to detect sensitive patterns in file paths and escalate risk level accordingly.

- **What happens if DeepSeek 3.2 API quota is exceeded during a research query?** The agent (configured with retries=2) should retry twice, then fail gracefully with an error indicating quota exceeded. OpenTelemetry should capture the quota error in traces. User should receive clear guidance to wait or increase quota.

- **How does the system handle tool execution timeouts?** Each MCP tool call should have a configurable timeout (e.g., WEBSEARCH_TIMEOUT=30 from env). If exceeded, the tool call should fail, the agent should detect this in tool_calls list, and may attempt alternate tools or report incomplete results with reduced confidence.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST initialize a Pydantic AI agent (ResearcherAgent) configured with DeepSeek 3.2 via Microsoft Azure AI Foundry using AzureModel with deployment_name="deepseek-v3", endpoint from AZURE_AI_FOUNDRY_ENDPOINT environment variable, and api_key from AZURE_AI_FOUNDRY_API_KEY environment variable

- **FR-002**: The ResearcherAgent MUST define a system prompt that explicitly lists its capabilities (web search, filesystem read, time context, memory search/store) and responsibilities (answer research queries, detect tool gaps, enforce risk-based approval)

- **FR-003**: The ResearcherAgent MUST enforce structured outputs by setting result_type=AgentResponse, where AgentResponse is a Pydantic model containing fields: answer (str), reasoning (str), tool_calls (List[dict]), and confidence (float between 0.0 and 1.0)

- **FR-004**: The ResearcherAgent MUST configure retries=2 for resilience against transient LLM API failures

- **FR-005**: The system MUST provide a setup_mcp_tools() function that initializes connections to all 3 MCP servers using StdioServerParameters: (1) Open-WebSearch MCP via command "npx -y @open-websearch/mcp-server", (2) mcp-server-filesystem in read-only mode, (3) custom time context MCP server

- **FR-006**: The system MUST expose a search_web(query: str, max_results: int = 10) tool via Open-WebSearch MCP that returns a List[dict] of search results, each containing at minimum: title, url, snippet

- **FR-007**: The system MUST expose a read_file(path: str) tool via mcp-server-filesystem that returns file contents as a string, restricted to read-only operations (no write, delete, or modify)

- **FR-008**: The system MUST expose a get_current_time(timezone: str = 'UTC') tool that returns a dict containing: timestamp (ISO 8601 format), timezone, and unix_epoch

- **FR-009**: The system MUST implement a ToolGapDetector class that accepts mcp_session: ClientSession in its constructor and provides a detect_missing_tools(task_description: str) method returning Optional[ToolGapReport]

- **FR-010**: The ToolGapDetector MUST query the MCP session for available tools via list_tools() API call and store the complete list of tool names and schemas

- **FR-011**: The ToolGapDetector MUST use the configured LLM (DeepSeek 3.2) to extract required capabilities from the task_description by analyzing the user's intent and identifying what actions would be needed to fulfill it

- **FR-012**: The ToolGapDetector MUST compare the required capabilities against available MCP tools and identify any missing tools needed to complete the task

- **FR-013**: The ToolGapDetector MUST return a ToolGapReport (Pydantic model) containing: missing_tools (List[str]), attempted_task (str copy of task_description), existing_tools_checked (List[str] of available tool names), when capability gaps are detected

- **FR-014**: The ToolGapDetector MUST return None when all required capabilities are available via existing MCP tools (no gaps detected)

- **FR-015**: The system MUST implement a categorize_action_risk(tool_name: str, parameters: dict) function that returns a RiskLevel enum value (REVERSIBLE, REVERSIBLE_WITH_DELAY, or IRREVERSIBLE)

- **FR-016**: The categorize_action_risk function MUST classify the following tools as REVERSIBLE: web_search, read_file, get_current_time, memory_search (search_memory)

- **FR-017**: The categorize_action_risk function MUST classify the following hypothetical tools as REVERSIBLE_WITH_DELAY: send_email, create_calendar_event, schedule_task (these tools may not exist yet but categorization logic must handle them)

- **FR-018**: The categorize_action_risk function MUST classify the following hypothetical tools as IRREVERSIBLE: delete_file, make_purchase, send_money, modify_production

- **FR-019**: The categorize_action_risk function MUST default to RiskLevel.IRREVERSIBLE for any unknown or unrecognized tool_name (safest assumption)

- **FR-020**: The system MUST implement a requires_approval(action: RiskLevel, confidence: float) function that returns a boolean indicating whether human approval is required before execution

- **FR-021**: The requires_approval function MUST return True (require approval) for all IRREVERSIBLE actions regardless of confidence score

- **FR-022**: The requires_approval function MUST return True (require approval) for REVERSIBLE_WITH_DELAY actions when confidence < 0.85

- **FR-023**: The requires_approval function MUST return False (auto-execute) for REVERSIBLE actions, enabling automatic execution with logging

- **FR-024**: The ResearcherAgent MUST register a search_memory tool using @researcher_agent.tool decorator that accepts ctx: RunContext[MemoryManager] and query: str, calls ctx.deps.semantic_search(query, top_k=5), and returns List[dict] with content and metadata from search results

- **FR-025**: The ResearcherAgent MUST register a store_memory tool using @researcher_agent.tool decorator that accepts ctx: RunContext[MemoryManager], content: str, and metadata: dict, calls ctx.deps.store_document(content, metadata), and returns the document ID as a string

- **FR-026**: The ResearcherAgent MUST be initialized with MemoryManager as a dependency via RunContext[MemoryManager] to enable access to semantic_search() and store_document() methods

- **FR-027**: The system MUST provide environment variable configuration for Azure AI Foundry credentials: AZURE_AI_FOUNDRY_ENDPOINT, AZURE_AI_FOUNDRY_API_KEY, AZURE_DEPLOYMENT_NAME (with example values in .env.example)

- **FR-028**: The system MUST provide environment variable configuration for MCP server settings: WEBSEARCH_ENGINE (options: google, duckduckgo, bing), WEBSEARCH_MAX_RESULTS (default: 10), WEBSEARCH_TIMEOUT (default: 30 seconds)

- **FR-029**: The system MUST provide environment variable configuration for OpenTelemetry: OTEL_EXPORTER_OTLP_ENDPOINT (default: http://localhost:4317), OTEL_SERVICE_NAME (must be: paias-agent-layer)

- **FR-030**: The system MUST instrument all MCP tool invocations with OpenTelemetry tracing using a @trace_tool_call decorator that creates span with attributes: tool_name, parameters (serialized), result_count, execution_duration_ms

- **FR-031**: The system MUST instrument all agent.run() calls with OpenTelemetry tracing, creating a span with attributes: confidence_score, tool_calls_count, task_description, result_type

- **FR-032**: All OpenTelemetry trace spans MUST be exported to the OTLP endpoint and be visible in Jaeger UI at localhost:16686 with service name "paias-agent-layer"

- **FR-033**: The system MUST ensure all tool inputs and outputs use Pydantic models for type safety (e.g., SearchWebParams, SearchWebResult, TimeContextResult)

- **FR-034**: The ResearcherAgent implementation MUST be model-agnostic, using only Pydantic AI abstractions (not vendor-specific APIs), to support swapping LLM providers without code changes

### Key Entities

- **AgentResponse**: Structured output from ResearcherAgent containing answer (str), reasoning (str explaining tool choices and logic), tool_calls (List[dict] with tool invocation details), confidence (float 0.0-1.0 indicating answer certainty)

- **ToolGapReport**: Diagnostic output when the agent detects missing capabilities, containing missing_tools (List[str] of tool names needed), attempted_task (str copy of user request), existing_tools_checked (List[str] of available tools that were evaluated)

- **RiskLevel**: Enum with three values (REVERSIBLE, REVERSIBLE_WITH_DELAY, IRREVERSIBLE) used to categorize tool action safety and determine approval requirements

- **MemoryManager**: Dependency injected into ResearcherAgent providing semantic_search(query: str, top_k: int) -> List[dict] and store_document(content: str, metadata: dict) -> str methods (defined in Spec 1: Core Foundation & Memory Layer)

- **MCP Tool Session**: ClientSession object managing connections to multiple MCP servers, providing list_tools() to query available capabilities and invoke_tool() for execution

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The ResearcherAgent successfully initializes with DeepSeek 3.2 via Azure AI Foundry and all 3 MCP tools (Open-WebSearch, filesystem, time) connect without errors within 10 seconds of startup

- **SC-002**: When asked "What is the capital of France?", the agent returns a correct answer within 5 seconds, triggers the web_search tool (visible in tool_calls), and returns confidence > 0.8

- **SC-003**: When asked "Retrieve my stock portfolio performance for Q3 2024" with no financial API tool available, the agent returns a ToolGapReport within 3 seconds containing missing_tools=["financial_data_api"] and does NOT fabricate data or claim task completion

- **SC-004**: All risk categorization test cases pass: web_search classified as REVERSIBLE, hypothetical send_email as REVERSIBLE_WITH_DELAY, hypothetical delete_file as IRREVERSIBLE, and unknown_tool defaults to IRREVERSIBLE

- **SC-005**: The requires_approval function correctly enforces approval rules in 100% of test cases: IRREVERSIBLE always requires approval, REVERSIBLE_WITH_DELAY requires approval if confidence < 0.85, REVERSIBLE auto-executes

- **SC-006**: The agent successfully stores research findings via store_memory() and later retrieves them via search_memory() with semantic match accuracy > 80% (measured by retrieving the correct stored document within top 5 results)

- **SC-007**: All unit tests pass with at least 80% code coverage as measured by pytest --cov-fail-under=80

- **SC-008**: When executing any research query, OpenTelemetry trace spans appear in Jaeger UI (localhost:16686) within 2 seconds, showing service name "paias-agent-layer" and all expected attributes (tool_name, parameters, confidence_score)

- **SC-009**: The system handles MCP tool failures gracefully: if web_search times out after 30 seconds, the agent returns an AgentResponse with confidence=0.0 and reasoning explaining the failure, without crashing

- **SC-010**: The agent completes a research query requiring memory integration (search + store) in under 10 seconds end-to-end, demonstrating performant integration with the memory layer from Spec 1
