/speckit.specify Build the ResearcherAgent with MCP Tools and Tool Gap Detection for the PAIAS Phase 1 Vertical Slice.

This layer includes:

1. Pydantic AI Agent Definition (agents/researcher.py)
   - Use DeepSeek 3.2 via Microsoft Azure AI Foundry as the reasoning engine (Constitution Article I.G)
   - Configure Azure AI Foundry endpoint with AzureModel from pydantic-ai:
     - deployment_name="deepseek-v3"
     - endpoint from AZURE_AI_FOUNDRY_ENDPOINT env var
     - api_key from AZURE_AI_FOUNDRY_API_KEY env var
   - System prompt that defines agent capabilities (web search, filesystem, time, memory) and responsibilities
   - Enforce structured outputs with result_type=AgentResponse
   - Configure retries=2 for resilience

2. MCP Tool Integration (3 Specific Tools)
   - Tool 1: Web Search via Open-WebSearch MCP
     - MCP Server: @open-websearch/mcp-server (no API key required)
     - Command: npx -y @open-websearch/mcp-server
     - Function: search_web(query, max_results=10) -> List[dict]
     - Risk Level: REVERSIBLE (read-only)
     - Auto-execute: Yes (if confidence > 0.5)
   
   - Tool 2: Filesystem Access via mcp-server-filesystem
     - Read-only mode (no write operations)
     - Function: read_file(path) -> str
     - Risk Level: REVERSIBLE (read-only)
     - Auto-execute: Yes
   
   - Tool 3: Time Context via custom MCP server
     - Function: get_current_time(timezone='UTC') -> dict
     - Risk Level: REVERSIBLE (no side effects)
     - Auto-execute: Yes
   
   - Create setup_mcp_tools() function to initialize all MCP client connections
   - Use StdioServerParameters for each MCP server

3. Tool Gap Detection Implementation (core/tool_gap_detector.py)
   - ToolGapDetector class that takes mcp_session: ClientSession
   - detect_missing_tools(task_description) -> Optional[ToolGapReport]
   - Query MCP for available tools via list_tools()
   - Use LLM to extract required capabilities from task description
   - Compare required vs. available tools
   - Return ToolGapReport with missing_tools, attempted_task, existing_tools_checked
   - Constitution Article II.G requirement: detect missing capabilities honestly (no hallucination)

4. Risk-Based Action Categorization (core/risk_assessment.py)
   - categorize_action_risk(tool_name, parameters) -> RiskLevel
     - REVERSIBLE: web_search, read_file, get_current_time, memory_search
     - REVERSIBLE_WITH_DELAY: send_email, create_calendar_event, schedule_task
     - IRREVERSIBLE: delete_file, make_purchase, send_money, modify_production
     - Default: IRREVERSIBLE (safest assumption)
   
   - requires_approval(action: RiskLevel, confidence: float) -> bool
     - IRREVERSIBLE: Always True (always require approval)
     - REVERSIBLE_WITH_DELAY: True if confidence < 0.85 (conditional approval)
     - REVERSIBLE: False (auto-execute with logging)
   - Constitution Article II.C requirement: Human-in-the-Loop for irreversible actions

5. Agent Integration with Memory (from Spec 1)
   - Add @researcher_agent.tool decorators for:
     - search_memory(ctx: RunContext[MemoryManager], query) -> List[dict]
       - Calls ctx.deps.semantic_search(query, top_k=5)
       - Returns content and metadata from results
     - store_memory(ctx: RunContext[MemoryManager], content, metadata) -> str
       - Calls ctx.deps.store_document(content, metadata)
       - Returns document ID
   - Connect agent to MemoryManager via RunContext dependency injection
   - Enables agent to search past knowledge and store new findings

6. Unit Tests with Mock MCP Servers (tests/test_researcher_agent.py)
   - test_agent_tool_gap_detection():
     - Mock MCP session with limited tools (web_search, read_file only)
     - Attempt task requiring missing tool (e.g., "Retrieve Q3 2024 financial data")
     - Assert ToolGapReport is returned with missing tool name
     - Verify agent doesn't hallucinate capabilities
   
   - test_risk_categorization():
     - Test REVERSIBLE: categorize_action_risk("web_search", {...}) == RiskLevel.REVERSIBLE
     - Test IRREVERSIBLE: categorize_action_risk("delete_file", {...}) == RiskLevel.IRREVERSIBLE
   
   - test_agent_basic_response():
     - Mock successful agent.run() call
     - Verify AgentResponse structure (answer, reasoning, tool_calls, confidence)
   
   - test_memory_integration():
     - Mock MemoryManager dependency
     - Verify agent can call search_memory and store_memory tools
   
   - Use AsyncMock for all MCP session mocking
   - 80%+ test coverage requirement (Constitution Article III.A)

7. Environment Configuration (.env.example)
   - Azure AI Foundry credentials:
     - AZURE_AI_FOUNDRY_ENDPOINT=https://your-resource.azure.ai/models
     - AZURE_AI_FOUNDRY_API_KEY=your-api-key-here
     - AZURE_DEPLOYMENT_NAME=deepseek-v3
   
   - MCP Server configuration:
     - WEBSEARCH_ENGINE=google (options: google, duckduckgo, bing)
     - WEBSEARCH_MAX_RESULTS=10
     - WEBSEARCH_TIMEOUT=30
   
   - OpenTelemetry settings (from Spec 1):
     - OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
     - OTEL_SERVICE_NAME=paias-agent-layer

8. OpenTelemetry Instrumentation
   - Add @trace_tool_call decorator for all MCP tool invocations
   - Instrument agent.run() calls with trace spans
   - Include span attributes: tool_name, parameters, result_count, confidence_score
   - Ensure all tool calls appear in Jaeger UI (Constitution Article II.D)

Constraints (from Constitution v2.1):
- Python 3.11+ with asyncio (Article I.A)
- Pydantic AI as atomic agent unit (Article I.C)
- DeepSeek 3.2 via Microsoft Azure AI Foundry (Article I.G)
- All tools via Model Context Protocol (MCP) - no hardcoded API clients (Article I.E)
- Human-in-the-Loop for irreversible actions (Article II.C)
- OpenTelemetry instrumentation for all tool calls (Article II.D)
- Tool Gap Detection capability (Article II.G)
- 80%+ test coverage with pytest (Article III.A)
- Type safety: All tool inputs/outputs must be Pydantic models
- Model-agnostic design: Agent code should work with any LLM via Pydantic AI adapter

Dependencies:
- Spec 1 (Core Foundation & Memory Layer) must be complete
- Pydantic models: AgentResponse, ToolGapReport, RiskLevel, ApprovalRequest (from Spec 1)
- MemoryManager class with semantic_search() and store_document() (from Spec 1)
- OpenTelemetry infrastructure with Jaeger (from Spec 1)
- PostgreSQL with pgvector for storing research findings (from Spec 1)

External Dependencies:
- Azure subscription with AI Foundry access and deployed DeepSeek 3.2 model
- Node.js/npm for Open-WebSearch MCP server (npx command)
- Python packages: pydantic-ai, azure-ai-inference, mcp (Python client)

Success Criteria:
- Agent successfully initializes with DeepSeek 3.2 via Azure AI Foundry
- All 3 MCP tools (Open-WebSearch, filesystem, time) connect and execute successfully
- Tool Gap Detection correctly identifies missing capabilities (returns ToolGapReport, doesn't hallucinate)
- Risk categorization logic passes all test cases (REVERSIBLE, REVERSIBLE_WITH_DELAY, IRREVERSIBLE)
- Agent returns structured AgentResponse with answer, reasoning, tool_calls, confidence
- Memory integration works: agent can search_memory() and store_memory()
- All tests pass with >80% coverage (pytest --cov-fail-under=80)
- Manual test: "What is the capital of France?" triggers web_search tool and returns correct answer
- Manual test: "Retrieve my stock portfolio performance" returns ToolGapReport (missing financial API tool)
- Jaeger UI (localhost:16686) shows trace spans for all agent tool calls with correct attributes
