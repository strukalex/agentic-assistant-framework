Based on the files, I can see that **Spec 1** (Core Foundation \& Memory Layer) established the database, memory abstraction, and observability infrastructure. Now let me explain **Spec 2** in detail and generate the command for you.[^1][^2][^3]

## Spec 2: The Agent \& Tooling Layer (ResearcherAgent with MCP Tools)

### What This Spec Delivers

Spec 2 builds the **"Brain"** (ResearcherAgent) and its **"Hands"** (MCP Tools). This spec creates your first intelligent agent that can actually perform actions in the world while being constitutionally compliant with human-in-the-loop, risk assessment, and tool gap detection.[^1]

### Core Components in Detail

#### 1. **ResearcherAgent (Pydantic AI Agent)**

This is your first atomic agent using Pydantic AI (Constitution Article I.C). The agent will:[^1]

- Use **DeepSeek 3.2 via Microsoft Azure AI Foundry** as its reasoning engine
- Always return structured `AgentResponse` with reasoning chains and confidence scores
- Integrate with the MemoryManager from Spec 1 to store/retrieve information
- Never hallucinate capabilities—honestly report when it lacks tools via `ToolGapReport`
- Follow a strict system prompt that defines its responsibilities and boundaries

**Key architectural decision**: The agent uses `result_type=AgentResponse` to enforce structured outputs, ensuring all agent responses are validated Pydantic models.[^1]

#### 2. **MCP Tool Integration (3 Specific Tools)**

These are the agent's capabilities, all accessed through the Model Context Protocol (Constitution Article I.E):[^1]

**Tool 1: Web Search** (`@web_search`)

- **MCP Server:** Open-WebSearch MCP server
- **Purpose:** Search external information sources
- **Risk Level:** `REVERSIBLE` (read-only operation)
- **Auto-execute:** Yes (if confidence > 0.5)
- **Returns:** List of search results with titles, URLs, snippets

**Tool 2: Filesystem Access** (`@filesystem`)

- **MCP Server:** `mcp-server-filesystem` (restricted to read-only)
- **Purpose:** Read local files/documents
- **Risk Level:** `REVERSIBLE` (read-only operation)
- **Auto-execute:** Yes
- **Returns:** File contents as string

**Tool 3: Time Context** (`@time`)

- **MCP Server:** Simple custom MCP server
- **Purpose:** Get current datetime in specified timezone
- **Risk Level:** `REVERSIBLE` (no side effects)
- **Auto-execute:** Yes
- **Returns:** Dict with timestamp, timezone, formatted strings

**MCP Client Setup Pattern**:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def setup_mcp_tools():
    # Open-WebSearch MCP server (no API key required)
    search_server = StdioServerParameters(
        command="npx",
        args=["-y", "@open-websearch/mcp-server"]
    )
    # Returns configured client session
```


#### 3. **Tool Gap Detection**

This implements Constitution Article II.G's requirement for agents to detect missing capabilities. The `ToolGapDetector` class:[^1]

- Queries the MCP session for available tools via `list_tools()`
- Uses an LLM to extract required capabilities from task descriptions
- Compares required vs. available tools
- Returns a structured `ToolGapReport` when gaps are detected (not an error or hallucination)

**Example**: If a user asks "Retrieve Q3 2024 financial data for AAPL" but no financial API tool exists, the agent returns:

```python
ToolGapReport(
    missing_tools=[{
        "name": "financial_data",
        "description": "Required for: Retrieve Q3 2024 financial data",
        "estimated_risk": "low",
        "proposed_implementation": "MCP server"
    }],
    attempted_task="Retrieve Q3 2024 financial data for AAPL",
    existing_tools_checked=["web_search", "read_file", "get_current_time"]
)
```


#### 4. **Risk-Based Action Categorization**

Implements Constitution Article II.C (Human-in-the-Loop). Two key functions:[^1]

**`categorize_action_risk(tool_name, parameters)`**:

- `REVERSIBLE`: Read-only operations (web_search, read_file, get_current_time) → auto-execute with logging
- `REVERSIBLE_WITH_DELAY`: Operations with undo windows (send_email, create_calendar_event) → require approval if confidence < 0.85
- `IRREVERSIBLE`: Dangerous operations (delete_file, make_purchase, send_money) → always require human approval

**`requires_approval(action, confidence)`**:

- Determines if the action needs to pause for human review
- Combines risk level with agent confidence score
- Ensures high-confidence reversible actions can auto-execute, while uncertain or dangerous actions block


#### 5. **Agent Integration with Memory**

Connects the agent to the MemoryManager from Spec 1:[^1]

```python
@researcher_agent.tool
async def search_memory(ctx: RunContext[MemoryManager], query: str):
    """Search long-term memory for relevant documents"""
    results = await ctx.deps.semantic_search(query, top_k=5)
    return [{"content": r.content, "metadata": r.metadata} for r in results]

@researcher_agent.tool
async def store_memory(ctx: RunContext[MemoryManager], content: str, metadata: dict):
    """Store information in long-term memory"""
    doc_id = await ctx.deps.store_document(content, metadata)
    return f"Stored with ID: {doc_id}"
```

This gives the agent **long-term memory** capabilities—it can search past knowledge and store new findings.

#### 6. **Unit Tests with Mock MCP Servers**

Comprehensive testing with mocked MCP sessions to verify:

- Tool gap detection works (missing tools are detected, not hallucinated)
- Risk categorization logic is correct
- Agent returns structured responses with confidence scores
- Memory integration functions properly

**Critical test case**:[^1]

```python
@pytest.mark.asyncio
async def test_agent_tool_gap_detection():
    """Test that agent detects missing financial data tool"""
    mock_session = AsyncMock()
    mock_session.list_tools.return_value = [
        {"name": "web_search"},
        {"name": "read_file"}
    ]
    
    result = await researcher_agent.run(
        "Retrieve Q3 2024 financial data for AAPL",
        deps=MemoryManager()
    )
    
    # Should return ToolGapReport, not hallucinate
    assert "financial_data" in result.data.missing_tools[^0]["name"]
```


### Constitutional Compliance

- **Article I.C**: Pydantic AI for atomic agents ✅
- **Article I.E**: All tools via MCP (no hardcoded tool clients) ✅
- **Article II.C**: Human-in-the-Loop with risk categorization ✅
- **Article II.D**: OpenTelemetry instrumentation for all tool calls ✅
- **Article II.G**: Tool Gap Detection capability ✅
- **Article III.A**: 80%+ test coverage with mock MCP servers ✅


### Why This Order?

Spec 2 **depends on Spec 1** because:

- The agent needs MemoryManager to store/retrieve information
- It uses the Pydantic models (`AgentResponse`, `ToolGapReport`, `RiskLevel`) defined in Spec 1
- OpenTelemetry infrastructure from Spec 1 traces all tool calls
- PostgreSQL stores research findings and conversation history

***

## Generate the Spec Command

Here's the complete command to generate Spec 2, similar to how Spec 1 was done:

```bash
spec-kit run specs/02-agent-tools.md
```

**Create the spec file at `specs/02-agent-tools.md` with this content:**

```markdown
# Spec: ResearcherAgent with MCP Tools and Tool Gap Detection

**Feature Branch:** `002-agent-tools`  
**Created:** 2025-12-22  
**Status:** Ready for Implementation  
**Depends On:** Spec 1 (Core Foundation & Memory Layer)

## Objective

Create the ResearcherAgent using Pydantic AI, integrate 3 MCP tools (web search, filesystem, time), and implement Tool Gap Detection as mandated by Constitution Article II.G.

## Constitution Constraints (mandatory)

**Source of truth:** `constitution.md` v2.1

This feature MUST comply with:
- **Article I.C:** Pydantic AI for atomic agents
- **Article I.E:** All tools via Model Context Protocol (MCP)
- **Article I.G:** DeepSeek 3.2 via Microsoft Azure AI Foundry as default model
- **Article II.C:** Human-in-the-Loop for irreversible actions  
- **Article II.D:** OpenTelemetry instrumentation throughout
- **Article II.G:** Tool Gap Detection capability
- **Article III.A:** 80%+ test coverage enforced

## Requirements

### 1. Pydantic AI Agent Definition

Create `agents/researcher.py`:

```

import os
from pydantic_ai import Agent, RunContext, ModelRetry
from pydantic_ai.models.azure import AzureModel
from models.common import AgentResponse, ToolGapReport, RiskLevel
from core.memory import MemoryManager

# Configure Azure AI Foundry endpoint for DeepSeek 3.2

azure_model = AzureModel(
deployment_name="deepseek-v3",
endpoint=os.getenv("AZURE_AI_FOUNDRY_ENDPOINT"),
api_key=os.getenv("AZURE_AI_FOUNDRY_API_KEY")
)

researcher_agent = Agent(
azure_model,  \# Constitution Article I.G - DeepSeek 3.2 via Azure AI Foundry
system_prompt="""You are the ResearcherAgent for a Personal AI Assistant.

Your capabilities:

- Search external information sources
- Access local filesystem (read-only)
- Query time/date context
- Store and retrieve from long-term memory

Your responsibilities:

- Always check memory before researching to avoid duplicate work
- Detect when you lack required tools and emit a ToolGapReport
- Categorize all actions by risk level (reversible/reversible-with-delay/irreversible)
- Never hallucinate capabilities—acknowledge gaps honestly

Output Format: Always return a structured AgentResponse with reasoning and confidence.""",
retries=2,
result_type=AgentResponse
)

```

**Rationale:** Constitution Article I.C requires Pydantic AI as the atomic agent unit. Article I.G specifies DeepSeek 3.2 via Azure AI Foundry for exceptional reasoning/code performance. The system prompt explicitly defines boundaries and honest capability reporting.

### 2. MCP Tool Integration (3 Specific Tools)

Integrate the following MCP tools using the `mcp` Python client:

**Tool 1: Web Search** (`@web_search`)
- **MCP Server:** Open-WebSearch MCP server
- **Function:** `search_web(query: str, max_results: int = 10) -> List[dict]`
- **Risk Level:** `REVERSIBLE` (read-only)
- **Auto-execute:** Yes (if confidence > 0.5)

**Tool 2: Filesystem Access** (`@filesystem`)
- **MCP Server:** Use `mcp-server-filesystem` (restricted to read-only mode)
- **Function:** `read_file(path: str) -> str`
- **Risk Level:** `REVERSIBLE` (read-only)
- **Auto-execute:** Yes

**Tool 3: Time Context** (`@time`)
- **MCP Server:** Simple custom MCP server for datetime operations
- **Function:** `get_current_time(timezone: str = 'UTC') -> dict`
- **Risk Level:** `REVERSIBLE`
- **Auto-execute:** Yes

**MCP Client Setup:**

```

import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def setup_mcp_tools():
"""Initialize MCP client connections"""
\# Open-WebSearch MCP server (no API key required)
search_server = StdioServerParameters(
command="npx",
args=["-y", "@open-websearch/mcp-server"],
env={
"WEBSEARCH_ENGINE": os.getenv("WEBSEARCH_ENGINE", "google")
}
)

    # Filesystem MCP server
    filesystem_server = StdioServerParameters(
        command="uvx",
        args=["mcp-server-filesystem"]
    )
    
    # Time MCP server (custom)
    time_server = StdioServerParameters(
        command="python",
        args=["-m", "mcp_servers.time"]
    )
    
    # Return configured client session
    ```

**Rationale:** Constitution Article I.E mandates all tool access via MCP (no hardcoded API clients). Open-WebSearch is open-source and requires no API keys.

### 3. Tool Gap Detection Implementation

Add detection logic to the agent:

```

class ToolGapDetector:
def __init__(self, mcp_session: ClientSession):
self.mcp_session = mcp_session

    async def detect_missing_tools(self, task_description: str) -> Optional[ToolGapReport]:
        """
        Compare task requirements against available MCP tools.
        Returns ToolGapReport if capabilities are missing.
        """
        # Query MCP for available tools
        available_tools = await self.mcp_session.list_tools()
        tool_names = [tool.name for tool in available_tools]
        
        # Analyze task requirements (use LLM to extract needed capabilities)
        required_capabilities = await self._extract_required_capabilities(task_description)
        
        # Detect gaps
        missing = [cap for cap in required_capabilities if cap not in tool_names]
        
        if missing:
            return ToolGapReport(
                missing_tools=[
                    {
                        "name": cap,
                        "description": f"Required for: {task_description}",
                        "estimated_risk": "low",  # Initial estimate
                        "proposed_implementation": "MCP server"
                    }
                    for cap in missing
                ],
                attempted_task=task_description,
                existing_tools_checked=tool_names
            )
        return None
    ```

**Rationale:** Constitution Article II.G requires agents to "detect missing capabilities and produce a machine-readable tool requirements report."

### 4. Risk-Based Action Categorization

Implement the risk assessment logic:

```

from models.common import RiskLevel, ApprovalRequest

def categorize_action_risk(tool_name: str, parameters: dict) -> RiskLevel:
"""
Categorize action based on reversibility (Constitution Article II.C)
"""
\# Read-only operations
if tool_name in ['web_search', 'read_file', 'get_current_time', 'memory_search']:
return RiskLevel.REVERSIBLE

    # Operations with delay window
    if tool_name in ['send_email', 'create_calendar_event', 'schedule_task']:
        return RiskLevel.REVERSIBLE_WITH_DELAY
    
    # Irreversible operations
    if tool_name in ['delete_file', 'make_purchase', 'send_money', 'modify_production']:
        return RiskLevel.IRREVERSIBLE
    
    # Default to safest assumption
    return RiskLevel.IRREVERSIBLE
    def requires_approval(action: RiskLevel, confidence: float) -> bool:
"""
Determine if human approval is required (Constitution Article II.C)
"""
if action == RiskLevel.IRREVERSIBLE:
return True  \# Always require approval

    if action == RiskLevel.REVERSIBLE_WITH_DELAY:
        return confidence < 0.85  # Conditional approval
    
    # REVERSIBLE actions auto-execute with logging
    return False
    ```

**Rationale:** Constitution Article II.C mandates Human-in-the-Loop for irreversible actions. This implements a confidence-weighted approval policy.

### 5. Agent Integration with Memory

Connect the agent to the MemoryManager from Spec 1:

```

@researcher_agent.tool
async def search_memory(ctx: RunContext[MemoryManager], query: str) -> List[dict]:
"""Search long-term memory for relevant documents"""
results = await ctx.deps.semantic_search(query, top_k=5)
return [{"content": r.content, "metadata": r.metadata} for r in results]

@researcher_agent.tool
async def store_memory(ctx: RunContext[MemoryManager], content: str, metadata: dict) -> str:
"""Store information in long-term memory"""
doc_id = await ctx.deps.store_document(content, metadata)
return f"Stored with ID: {doc_id}"

```

**Rationale:** Agents need persistent memory to avoid redundant research and build knowledge over time.

### 6. Unit Tests with Mock MCP Servers

Create comprehensive tests (Constitution Article III.A):

```


# tests/test_researcher_agent.py

import pytest
from unittest.mock import AsyncMock
from agents.researcher import researcher_agent
from models.common import AgentResponse

@pytest.mark.asyncio
async def test_agent_tool_gap_detection():
"""Test that agent detects missing financial data tool"""
\# Mock MCP session with limited tools
mock_session = AsyncMock()
mock_session.list_tools.return_value = [
{"name": "web_search"},  \# Open-WebSearch MCP
{"name": "read_file"}
]

    # Attempt task requiring missing tool
    result = await researcher_agent.run(
        "Retrieve Q3 2024 financial data for AAPL",
        deps=MemoryManager()
    )
    
    # Should return ToolGapReport, not hallucinate
    assert "financial_data" in result.data.missing_tools["name"]
    @pytest.mark.asyncio
async def test_risk_categorization():
"""Test that read operations are marked reversible"""
risk = categorize_action_risk("web_search", {"query": "test"})
assert risk == RiskLevel.REVERSIBLE

    risk = categorize_action_risk("delete_file", {"path": "/data/important.txt"})
    assert risk == RiskLevel.IRREVERSIBLE
    ```

**Rationale:** Mock MCP servers allow testing without external dependencies. Critical to verify honest capability reporting vs. hallucination.

## Constraints

- **Framework:** Pydantic AI only (Constitution Article I.C)
- **Model:** DeepSeek 3.2 via Azure AI Foundry (Constitution Article I.G)
- **Tool Protocol:** All tools via MCP (Constitution Article I.E)
- **Testing:** 80%+ coverage with mock MCP servers
- **Type Safety:** All tool inputs/outputs must be Pydantic models
- **Observability:** Instrument all tool calls with OpenTelemetry

## Dependencies

### Azure AI Foundry Setup
- Azure subscription with AI Foundry access
- Deployed DeepSeek 3.2 model endpoint
- Environment variables:
```

AZURE_AI_FOUNDRY_ENDPOINT=https://your-resource.azure.ai/models
AZURE_AI_FOUNDRY_API_KEY=your-api-key-here
AZURE_DEPLOYMENT_NAME=deepseek-v3

```

### MCP Servers
- **Open-WebSearch**: Install via `npm install -g @open-websearch/mcp-server` or use `npx`
- **Filesystem**: Install via `uvx mcp-server-filesystem`
- **Time**: Custom implementation (create in Phase 2)

### Python Dependencies
Add to `pyproject.toml`:
```

[tool.poetry.dependencies]
pydantic-ai = "^0.0.14"  \# With Azure support
azure-ai-inference = "^1.0.0"
mcp = "^1.0.0"

```

## Success Criteria

1. ✅ Agent successfully calls all 3 MCP tools in a test scenario
2. ✅ Tool Gap Detection correctly identifies missing capabilities
3. ✅ Risk categorization logic passes all test cases
4. ✅ Agent returns structured `AgentResponse` with confidence scores
5. ✅ Memory integration works (agent can store/retrieve documents)
6. ✅ All tests pass with >80% coverage
7. ✅ DeepSeek 3.2 model responds via Azure AI Foundry endpoint
8. ✅ Open-WebSearch MCP performs web searches without API keys
```


***

## Between-Specs Validation Workflow (Run After Spec 2)

### 1. ✅ **Verification:**

**Unit Tests:**

```bash
pytest tests/test_researcher_agent.py --cov-fail-under=80
```

**Manual Validation:**

Run standalone test script:

```python
# test_agent_standalone.py
import asyncio
from agents.researcher import researcher_agent
from core.memory import MemoryManager

async def main():
    memory = MemoryManager()
    result = await researcher_agent.run(
        "What is the capital of France?",
        deps=memory
    )
    print(f"Answer: {result.data.answer}")
    print(f"Confidence: {result.data.confidence}")
    print(f"Tools Used: {result.data.tool_calls}")

asyncio.run(main())
```

- Verify agent actually called `web_search` tool via Open-WebSearch MCP (check logs)
- Verify DeepSeek 3.2 model is being called (check Azure AI Foundry logs)
- Test Tool Gap Detection:

```python
result = await researcher_agent.run(
    "Retrieve my stock portfolio performance",
    deps=memory
)
# Should return ToolGapReport mentioning missing "portfolio_api" tool
```

- Check Jaeger for tool call traces


### 2. ✅ **Commit:**

```bash
git add . && git commit -m "feat(phase1): researcher agent with MCP tools and gap detection"
```


### 3. ✅ **Update Context:**

Document in `project-context.md`:

- Azure AI Foundry endpoint details
- DeepSeek 3.2 model deployment name
- Which MCP servers are installed (Open-WebSearch, filesystem, time)
- Any tool limitations or rate limits

***

This spec completes the **"Brain"** of your system, giving it the ability to think (DeepSeek 3.2 agent), act (MCP tools via Open-WebSearch, filesystem, time), remember (memory integration), and honestly report its limitations (tool gap detection).[^1]

<div align="center">⁂</div>

[^1]: phase-1-specs.md

[^2]: spec.md

[^3]: plan.md

