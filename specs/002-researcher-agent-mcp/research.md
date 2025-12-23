# Research: ResearcherAgent with MCP Tools and Tool Gap Detection

**Feature**: 002-researcher-agent-mcp
**Date**: 2025-12-22
**Purpose**: Resolve technical unknowns before implementation

## Research Questions

### RQ-001: Pydantic AI + Azure AI Foundry Integration

**Question**: How to configure Pydantic AI to use DeepSeek 3.2 via Microsoft Azure AI Foundry?

**Decision**: Use `pydantic_ai.models.azure.AzureModel` with model name "deepseek-v3"

**Rationale**:
- Pydantic AI 1.0+ has native Azure AI Foundry support via `pydantic_ai.models.azure`
- DeepSeek 3.2 is deployed in Azure AI Foundry model catalog with model ID "deepseek-v3"
- Requires environment variables: `AZURE_AI_FOUNDRY_ENDPOINT` and `AZURE_AI_FOUNDRY_API_KEY`
- Model initialization:
  ```python
  from pydantic_ai import Agent
  from pydantic_ai.models.azure import AzureModel

  model = AzureModel(
      model_name="deepseek-v3",
      endpoint=os.getenv("AZURE_AI_FOUNDRY_ENDPOINT"),
      api_key=os.getenv("AZURE_AI_FOUNDRY_API_KEY")
  )

  agent = Agent(
      model=model,
      result_type=AgentResponse,
      retries=2
  )
  ```

**Alternatives Considered**:
- Using Azure OpenAI wrapper: Rejected because DeepSeek is not part of Azure OpenAI service
- Using generic HTTP adapter: Rejected because Azure-specific authentication is complex

**References**:
- Pydantic AI Azure docs: https://ai.pydantic.dev/models/azure/
- Azure AI Foundry model catalog: https://learn.microsoft.com/azure/ai-foundry/

---

### RQ-002: MCP Python Client Integration

**Question**: What is the best way to integrate MCP servers with Pydantic AI agents in Python?

**Decision**: Use `mcp` Python package with async context managers for MCP client sessions

**Rationale**:
- Official Python MCP SDK: `mcp` package provides `ClientSession` for managing MCP server connections
- Integration pattern:
  ```python
  from mcp import ClientSession, StdioServerParameters
  from mcp.client.stdio import stdio_client

  async def setup_mcp_tools():
      # Open-WebSearch MCP server
      websearch_params = StdioServerParameters(
          command="npx",
          args=["-y", "@open-websearch/mcp-server"],
          env={"WEBSEARCH_ENGINE": os.getenv("WEBSEARCH_ENGINE", "google")}
      )

      async with stdio_client(websearch_params) as (read, write):
          async with ClientSession(read, write) as session:
              await session.initialize()
              # Register tools with Pydantic AI agent
              tools = await session.list_tools()
              return session, tools
  ```
- Lifecycle management: Use async context managers to ensure proper cleanup
- Tool discovery: `session.list_tools()` returns all available MCP tools with schemas

**Alternatives Considered**:
- LangChain MCP integration: Rejected per Constitution Article I.B (avoid LangChain as primary framework)
- Custom HTTP bridge: Rejected because stdio communication is simpler and well-supported

**References**:
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- MCP specification: https://modelcontextprotocol.io/

---

### RQ-003: Open-WebSearch MCP Server Configuration

**Question**: How to configure and use @open-websearch/mcp-server with the MCP Python client?

**Decision**: Use stdio transport with npx command; supports Google, DuckDuckGo, and Bing engines

**Rationale**:
- No API key required (uses public search engines with rate limiting)
- Supports multiple engines via WEBSEARCH_ENGINE env var
- Tool schema:
  ```json
  {
    "name": "search_web",
    "description": "Search the web for information",
    "inputSchema": {
      "type": "object",
      "properties": {
        "query": {"type": "string"},
        "max_results": {"type": "integer", "default": 10}
      }
    }
  }
  ```
- Returns JSON array of results with title, url, snippet fields
- Environment variables:
  - `WEBSEARCH_ENGINE`: google (default) | duckduckgo | bing
  - `WEBSEARCH_MAX_RESULTS`: Default 10 results
  - `WEBSEARCH_TIMEOUT`: Default 30 seconds

**Alternatives Considered**:
- Tavily API: Rejected because requires API key (violates "no hardcoded integrations" principle)
- Google Custom Search API: Rejected because requires API key
- SerpAPI: Rejected because requires paid subscription

**References**:
- Open-WebSearch MCP: https://github.com/open-websearch/mcp-server
- MCP stdio transport: https://modelcontextprotocol.io/docs/concepts/transports

---

### RQ-004: OpenTelemetry Instrumentation for Async Agents

**Question**: How to instrument async Pydantic AI agents with OpenTelemetry for full observability?

**Decision**: Use `opentelemetry-api` with custom decorators and manual span management

**Rationale**:
- Pattern for instrumenting tool calls:
  ```python
  from opentelemetry import trace
  from opentelemetry.trace import Status, StatusCode

  tracer = trace.get_tracer(__name__)

  def trace_tool_call(func):
      async def wrapper(*args, **kwargs):
          with tracer.start_as_current_span(f"mcp_tool_call:{func.__name__}") as span:
              span.set_attribute("tool_name", func.__name__)
              span.set_attribute("parameters", str(kwargs))
              try:
                  result = await func(*args, **kwargs)
                  span.set_attribute("result_count", len(result) if isinstance(result, list) else 1)
                  return result
              except Exception as e:
                  span.set_status(Status(StatusCode.ERROR))
                  span.set_attribute("error_type", type(e).__name__)
                  span.set_attribute("error_message", str(e))
                  raise
      return wrapper
  ```
- Agent run instrumentation:
  ```python
  async def run_with_tracing(agent, task):
      with tracer.start_as_current_span("agent_run") as span:
          span.set_attribute("task_description", task)
          result = await agent.run(task)
          span.set_attribute("confidence_score", result.data.confidence)
          span.set_attribute("tool_calls_count", len(result.data.tool_calls))
          return result
  ```
- OTLP exporter configuration:
  ```python
  from opentelemetry.sdk.trace import TracerProvider
  from opentelemetry.sdk.trace.export import BatchSpanProcessor
  from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

  provider = TracerProvider()
  processor = BatchSpanProcessor(OTLPSpanExporter(
      endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
  ))
  provider.add_span_processor(processor)
  trace.set_tracer_provider(provider)
  ```

**Alternatives Considered**:
- Auto-instrumentation: Rejected because Pydantic AI is too new for auto-instrumentation support
- Logfire integration: Deferred to Phase 2 (Pydantic AI has native Logfire support but adds complexity)

**References**:
- OpenTelemetry Python: https://opentelemetry.io/docs/languages/python/
- OTLP exporter: https://opentelemetry-python.readthedocs.io/en/latest/exporter/otlp/otlp.html

---

### RQ-005: Tool Gap Detection Implementation Pattern

**Question**: How should the ToolGapDetector analyze tasks and compare against available MCP tools?

**Decision**: Use LLM-based capability extraction + schema matching against MCP tool list

**Rationale**:
- Two-phase detection:
  1. **Capability Extraction**: Use LLM to parse task description and extract required capabilities
     - Example: "Retrieve my stock portfolio for Q3 2024" → ["financial_data_retrieval", "account_access"]
  2. **Schema Matching**: Compare required capabilities against MCP tool schemas
     - Check tool names, descriptions, and input schemas
     - Use fuzzy matching for similar capabilities (e.g., "search_web" matches "web_search_capability")

- Implementation pattern:
  ```python
  class ToolGapDetector:
      def __init__(self, mcp_session: ClientSession):
          self.mcp_session = mcp_session
          self.available_tools = None

      async def detect_missing_tools(self, task_description: str) -> Optional[ToolGapReport]:
          # Phase 1: Get available tools
          if self.available_tools is None:
              self.available_tools = await self.mcp_session.list_tools()

          # Phase 2: Extract required capabilities via LLM
          prompt = f"""Analyze this task and list required capabilities:
          Task: {task_description}

          Return JSON array of capability names (e.g., ["web_search", "file_access"]).
          """
          required_capabilities = await self._extract_capabilities(prompt)

          # Phase 3: Match capabilities to tools
          available_capability_names = [tool.name for tool in self.available_tools]
          missing = [cap for cap in required_capabilities if cap not in available_capability_names]

          if missing:
              return ToolGapReport(
                  missing_tools=missing,
                  attempted_task=task_description,
                  existing_tools_checked=available_capability_names
              )
          return None
  ```

- Fallback strategy: If LLM fails to extract capabilities, return conservative ToolGapReport with warning

**Alternatives Considered**:
- Rule-based keyword matching: Rejected because too brittle (e.g., "get stock data" wouldn't match "financial API")
- Embedding similarity: Rejected because adds complexity and requires vector DB for tool schemas

**References**:
- MCP tool discovery: https://modelcontextprotocol.io/docs/concepts/tools
- LLM capability extraction pattern: Common practice in agentic systems

---

### RQ-006: Risk Assessment Implementation

**Question**: How to implement categorize_action_risk() and requires_approval() functions?

**Decision**: Use static mapping table for known tools + conservative default for unknowns

**Rationale**:
- Risk mapping table:
  ```python
  from enum import Enum

  class RiskLevel(str, Enum):
      REVERSIBLE = "reversible"
      REVERSIBLE_WITH_DELAY = "reversible_with_delay"
      IRREVERSIBLE = "irreversible"

  TOOL_RISK_MAP = {
      # Reversible (read-only, no side effects)
      "web_search": RiskLevel.REVERSIBLE,
      "search_web": RiskLevel.REVERSIBLE,
      "read_file": RiskLevel.REVERSIBLE,
      "get_current_time": RiskLevel.REVERSIBLE,
      "memory_search": RiskLevel.REVERSIBLE,
      "search_memory": RiskLevel.REVERSIBLE,

      # Reversible with delay (can be undone within time window)
      "send_email": RiskLevel.REVERSIBLE_WITH_DELAY,
      "create_calendar_event": RiskLevel.REVERSIBLE_WITH_DELAY,
      "schedule_task": RiskLevel.REVERSIBLE_WITH_DELAY,

      # Irreversible (permanent consequences)
      "delete_file": RiskLevel.IRREVERSIBLE,
      "make_purchase": RiskLevel.IRREVERSIBLE,
      "send_money": RiskLevel.IRREVERSIBLE,
      "modify_production": RiskLevel.IRREVERSIBLE,
  }

  def categorize_action_risk(tool_name: str, parameters: dict) -> RiskLevel:
      # Check static mapping first
      if tool_name in TOOL_RISK_MAP:
          return TOOL_RISK_MAP[tool_name]

      # Parameter inspection for context-dependent risk
      if tool_name == "read_file" and any(
          sensitive in parameters.get("path", "").lower()
          for sensitive in ["/etc/shadow", "api_key", "secret", "credentials"]
      ):
          return RiskLevel.REVERSIBLE_WITH_DELAY  # Escalate sensitive file reads

      # Conservative default: treat unknown tools as irreversible
      return RiskLevel.IRREVERSIBLE

  def requires_approval(action: RiskLevel, confidence: float) -> bool:
      if action == RiskLevel.IRREVERSIBLE:
          return True  # Always require approval
      elif action == RiskLevel.REVERSIBLE_WITH_DELAY:
          return confidence < 0.85  # Conditional approval
      else:  # REVERSIBLE
          return False  # Auto-execute with logging
  ```

**Alternatives Considered**:
- LLM-based risk assessment: Rejected because too slow and unreliable for production safety checks
- Parameter-only inspection: Rejected because tool name is primary risk indicator

**References**:
- Constitution Article II.C: Human-in-the-Loop by Default
- Risk categorization best practices: Industry-standard safety patterns

---

### RQ-007: Memory Integration via Dependency Injection

**Question**: How to connect ResearcherAgent to MemoryManager from Spec 001 using Pydantic AI patterns?

**Decision**: Use Pydantic AI's RunContext with MemoryManager as dependency

**Rationale**:
- Pydantic AI dependency injection pattern:
  ```python
  from pydantic_ai import Agent, RunContext
  from src.memory.manager import MemoryManager  # From Spec 001

  researcher_agent = Agent[MemoryManager, AgentResponse](
      model=model,
      result_type=AgentResponse,
      retries=2
  )

  @researcher_agent.tool
  async def search_memory(ctx: RunContext[MemoryManager], query: str) -> List[dict]:
      """Search semantic memory for relevant past knowledge."""
      results = await ctx.deps.semantic_search(query, top_k=5)
      return [
          {"content": r.content, "metadata": r.metadata}
          for r in results
      ]

  @researcher_agent.tool
  async def store_memory(ctx: RunContext[MemoryManager], content: str, metadata: dict) -> str:
      """Store new research findings in memory."""
      doc_id = await ctx.deps.store_document(content, metadata)
      return doc_id

  # Agent invocation with dependency
  memory_manager = MemoryManager(db_connection)  # From Spec 001
  result = await researcher_agent.run(
      "What are Python async best practices?",
      deps=memory_manager
  )
  ```
- Type safety: RunContext[MemoryManager] provides IDE autocomplete and type checking
- Testability: Easy to inject mock MemoryManager for unit tests

**Alternatives Considered**:
- Global MemoryManager instance: Rejected because breaks testability and async safety
- Agent subclass with __init__: Rejected because Pydantic AI agents are stateless by design

**References**:
- Pydantic AI dependency injection: https://ai.pydantic.dev/dependencies/
- RunContext docs: https://ai.pydantic.dev/api/agent/#pydantic_ai.Agent.run

---

## Summary of Decisions

| Research Question | Decision | Impact |
|---|---|---|
| RQ-001: Azure AI Foundry | Use `AzureModel` with "deepseek-v3" | Agent initialization code |
| RQ-002: MCP Integration | Use `mcp` Python SDK with async context managers | MCP client setup |
| RQ-003: Open-WebSearch | Use stdio transport with npx; supports Google/DuckDuckGo/Bing | Web search tool config |
| RQ-004: OpenTelemetry | Custom decorators + manual span management | Observability implementation |
| RQ-005: Tool Gap Detection | LLM capability extraction + schema matching | ToolGapDetector class |
| RQ-006: Risk Assessment | Static mapping + parameter inspection + conservative defaults | Risk categorization logic |
| RQ-007: Memory Integration | Pydantic AI RunContext dependency injection | Agent tool definitions |

## Open Questions

None. All technical unknowns resolved.

## Next Steps

Proceed to Phase 1: Design & Contracts
- Generate data-model.md with Pydantic model definitions
- Generate OpenAPI contract for agent Python API
- Generate quickstart.md with setup instructions
