# Phase 1 Complete Execution Plan
**Personal AI Assistant System (PAIAS) - Foundation & Vertical Slice**

**Version:** 2.0 (Enhanced with Constitutional Compliance)  
**Date:** December 21, 2025  
**Status:** Ready for Implementation  
**Governed By:** constitution.md v2.0

## Executive Summary

This plan breaks Phase 1 into **4 distinct, sequential specifications** that build the complete vertical slice: Foundation → Brain → Body → Face. Each spec must be fully validated before proceeding to the next.

**Success Criteria:** At completion, you will have a working "DailyTrendingResearch" system where a user submits a topic, the agent researches using MCP tools, Windmill orchestrates the workflow with LangGraph handling complex reasoning loops, and a Streamlit UI displays streaming results with full observability.

---

## Constitutional Compliance Checklist

Before running any `/specify` command, verify alignment with constitution.md:

- ✅ **Article I.A:** Python 3.11+ with async/await
- ✅ **Article I.B:** Windmill (DAG) + LangGraph (loops) hybrid orchestration
- ✅ **Article I.C:** Pydantic AI for atomic agents
- ✅ **Article I.D:** PostgreSQL + pgvector for memory
- ✅ **Article I.E:** All tools via Model Context Protocol (MCP)
- ✅ **Article II.C:** Human-in-the-Loop for irreversible actions
- ✅ **Article II.D:** OpenTelemetry instrumentation throughout
- ✅ **Article II.G:** Tool Gap Detection capability
- ✅ **Article III.A:** 80%+ test coverage enforced

---

## The Four-Spec Execution Plan

### Spec 1: The Core Foundation & Memory Layer

**Goal:** Establish the database, telemetry, shared data models, and memory abstraction. Nothing else works without this.

**Command:**
```

spec-kit run specs/01-foundation-memory.md

```

**Spec Content:**
```


# Spec: Core Foundation and Memory Layer

## Objective

Build the foundational infrastructure for the PAIAS Phase 1 Vertical Slice.

## Requirements

### 1. PostgreSQL Database Schema with pgvector

- **PostgreSQL 15+** with `pgvector` extension enabled
- **Tables:**
    - `sessions`: User interaction sessions
        - `id`: UUID (primary key)
        - `user_id`: String
        - `created_at`: Timestamp
        - `metadata`: JSONB (tags, context)
    - `messages`: Chat history
        - `id`: UUID (primary key)
        - `session_id`: UUID (foreign key to sessions)
        - `role`: Enum ('user', 'assistant', 'system')
        - `content`: Text
        - `created_at`: Timestamp
    - `documents`: Document storage with embeddings
        - `id`: UUID (primary key)
        - `content`: Text
        - `embedding`: Vector(1536) using pgvector (OpenAI dimension)
        - `metadata`: JSONB (source, tags, permissions)
        - `created_at`: Timestamp
        - `updated_at`: Timestamp


### 2. Memory Manager Abstraction Layer

Create a `MemoryManager` class (in `core/memory.py`) that abstracts all database operations:

```python
class MemoryManager:
    async def store_document(self, content: str, metadata: dict) -> UUID:
        """Store document with auto-generated embedding"""
        
    async def semantic_search(self, query: str, top_k: int = 5) -> List[Document]:
        """Vector similarity search using pgvector"""
        
    async def store_message(self, session_id: UUID, role: str, content: str) -> UUID:
        """Store chat message"""
        
    async def get_conversation_history(self, session_id: UUID, limit: int = 20) -> List[Message]:
        """Retrieve recent conversation"""
        
    async def temporal_query(self, date_range: tuple, filters: dict = None) -> List[Document]:
        """Time-based document retrieval"""
```

**Rationale:** This abstraction ensures Constitution Article II.E compliance—agents never import database drivers directly.

### 3. Base Pydantic Models (Shared Contracts)

Create shared data models in `models/common.py`:

```python
from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Optional
from datetime import datetime

class RiskLevel(str, Enum):
    REVERSIBLE = "reversible"
    REVERSIBLE_WITH_DELAY = "reversible_with_delay"
    IRREVERSIBLE = "irreversible"

class AgentResponse(BaseModel):
    answer: str = Field(description="Natural language response to user")
    reasoning: str = Field(description="Chain of thought explanation")
    tool_calls: List[str] = Field(default_factory=list, description="Names of tools invoked")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ToolGapReport(BaseModel):
    missing_tools: List[dict] = Field(description="Specifications for missing capabilities")
    attempted_task: str = Field(description="The task that revealed the gap")
    existing_tools_checked: List[str] = Field(description="Tools queried via MCP")
    proposed_mcp_server: Optional[str] = None

class ApprovalRequest(BaseModel):
    action_type: RiskLevel
    action_description: str
    confidence: float
    tool_name: str
    parameters: dict
    requires_immediate_approval: bool
```

**Rationale:** Constitution Article I.C requires "Pydantic validation at every boundary."

### 4. OpenTelemetry Configuration

Set up distributed tracing infrastructure:

- Initialize OpenTelemetry SDK with Jaeger exporter (local deployment)
- Create base instrumentation utilities in `core/telemetry.py`:
    - `trace_agent_execution()` decorator
    - `trace_tool_call()` decorator
    - `trace_memory_operation()` decorator
- Configure 100% sampling for Phase 1 (Constitution Article II.D requirement)
- Add Jaeger service to `docker-compose.yml` (port 16686 for UI)

**Success Metric:** Every database operation and future tool call generates a trace span.

### 5. Docker Compose Infrastructure

Create `docker-compose.yml` with:

- PostgreSQL 15 with pgvector extension pre-installed
- Jaeger (all-in-one image) for trace collection
- Environment variable configuration for connection strings


### 6. Database Migrations

Use Alembic (Constitution Article III.D) to manage schema:

- Initial migration for all three tables
- Include `pgvector` extension setup in migration
- Test rollback capability


## Constraints

- **Language:** Python 3.11+ with asyncio (Constitution Article I.A)
- **Database Driver:** `asyncpg` for async PostgreSQL access
- **ORM:** SQLAlchemy 2.0 async
- **Testing:** 80%+ coverage with pytest (Constitution Article III.A)
- **Type Safety:** Strict mypy checks on all Pydantic models


## Success Criteria

1. `docker-compose up` starts PostgreSQL + Jaeger successfully
2. Can connect to DB and insert/query a vector embedding
3. `MemoryManager.semantic_search()` returns relevant documents
4. All Pydantic models validate correctly with test data
5. Jaeger UI shows trace spans for database operations
```

---

**Between-Specs Validation Workflow (Run After Spec 1):**

1. ✅ **Run /plan:** Generate technical architecture
2. ✅ **Run /tasks:** Break into checklist items  
3. ✅ **Implement & Loop:** Complete all tasks
4. ✅ **Verification:**
   - **Unit Tests:** `pytest --cov=core --cov-fail-under=80`
   - **Manual Validation:**
     - Run `docker-compose up -d`
     - Connect to PostgreSQL: `psql -U postgres -d paias`
     - Verify tables exist: `\dt`
     - Verify pgvector: `SELECT * FROM pg_extension WHERE extname='vector';`
     - Test `MemoryManager`:
       ```
       import asyncio
       from core.memory import MemoryManager
       
       async def test():
           mm = MemoryManager()
           doc_id = await mm.store_document("Test content", {"source": "manual"})
           results = await mm.semantic_search("test query", top_k=3)
           print(f"Found {len(results)} documents")
       
       asyncio.run(test())
       ```
     - Open Jaeger UI: `http://localhost:16686` and verify trace appears
5. ✅ **Commit:** `git add . && git commit -m "feat(phase1): foundation layer with memory abstraction"`
6. ✅ **Update Context:** Update `project-context.md` with actual table names, any deviations
```

---

### Spec 2: The Agent & Tooling Layer

**Goal:** Build the "Brain" (ResearcherAgent) and its "Hands" (MCP Tools). Implement Tool Gap Detection.

**Command:**

`spec-kit run specs/02-agent-tools.md`

**Spec Content:**

# Spec: ResearcherAgent with MCP Tools and Tool Gap Detection

## Objective

Create the `ResearcherAgent` using Pydantic AI, integrate MCP tools, and implement Tool Gap Detection as mandated by Constitution Article II.G.

## Requirements

### 1. Pydantic AI Agent Definition

Create `agents/researcher.py`:

```python
from pydantic_ai import Agent, RunContext, ModelRetry
from models.common import AgentResponse, ToolGapReport, RiskLevel
from core.memory import MemoryManager

researcher_agent = Agent(
    'anthropic:claude-3-5-sonnet',  # Constitution Article I.G
    system_prompt="""You are the ResearcherAgent for a Personal AI Assistant.

Your capabilities:
- Search external information sources
- Access local filesystem (read-only)
- Query time/date context
- Store and retrieve from long-term memory

Your responsibilities:
- Always check memory before researching to avoid duplicate work
- Detect when you lack required tools and emit a ToolGapReport
- Categorize all actions by risk level (reversible/reversible_with_delay/irreversible)
- Never hallucinate capabilities—acknowledge gaps honestly

Output Format: Always return a structured AgentResponse with reasoning and confidence.""",
    retries=2,
    result_type=AgentResponse
)
```


### 2. MCP Tool Integration (3 Specific Tools)

Integrate the following MCP tools using the `mcp` Python client:

**Tool 1: Web Search** (`@web_search`)

- MCP Server: Use Tavily or Brave Search MCP server
- Function: `search_web(query: str, max_results: int = 10) -> List[dict]`
- Risk Level: `REVERSIBLE` (read-only)
- Auto-execute: Yes (if confidence > 0.5)

**Tool 2: Filesystem Access** (`@filesystem`)

- MCP Server: Use `mcp-server-filesystem` (restricted to read-only mode)
- Function: `read_file(path: str) -> str`
- Risk Level: `REVERSIBLE` (read-only)
- Auto-execute: Yes

**Tool 3: Time Context** (`@time`)

- MCP Server: Simple custom MCP server for datetime operations
- Function: `get_current_time(timezone: str = 'UTC') -> dict`
- Risk Level: `REVERSIBLE`
- Auto-execute: Yes

**MCP Client Setup:**

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def setup_mcp_tools():
    """Initialize MCP client connections"""
    # Connect to web search MCP server
    search_server = StdioServerParameters(
        command="uvx",
        args=["mcp-server-tavily"]
    )
    
    # Similar setup for filesystem and time servers
    # Return configured client session
```


### 3. Tool Gap Detection Implementation

Add detection logic to the agent:

```python
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

```python
from models.common import RiskLevel, ApprovalRequest

def categorize_action_risk(tool_name: str, parameters: dict) -> RiskLevel:
    """
    Categorize action based on reversibility (Constitution Article II.C)
    """
    # Read-only operations
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
        return True  # Always require approval
    
    if action == RiskLevel.REVERSIBLE_WITH_DELAY:
        return confidence < 0.85  # Conditional approval
    
    # REVERSIBLE actions auto-execute with logging
    return False
```


### 5. Agent Integration with Memory

Connect the agent to the MemoryManager from Spec 1:

```python
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


### 6. Unit Tests with Mock MCP Servers

Create comprehensive tests (Constitution Article III.A):

```python
# tests/test_researcher_agent.py
import pytest
from unittest.mock import AsyncMock
from agents.researcher import researcher_agent
from models.common import AgentResponse

@pytest.mark.asyncio
async def test_agent_tool_gap_detection():
    """Test that agent detects missing financial data tool"""
    # Mock MCP session with limited tools
    mock_session = AsyncMock()
    mock_session.list_tools.return_value = [
        {"name": "web_search"},
        {"name": "read_file"}
    ]
    
    # Attempt task requiring missing tool
    result = await researcher_agent.run(
        "Retrieve Q3 2024 financial data for AAPL",
        deps=MemoryManager()
    )
    
    # Should return ToolGapReport, not hallucinate
    assert "financial_data" in result.data.missing_tools[0]["name"]

@pytest.mark.asyncio
async def test_risk_categorization():
    """Test that read operations are marked reversible"""
    risk = categorize_action_risk("web_search", {"query": "test"})
    assert risk == RiskLevel.REVERSIBLE
    
    risk = categorize_action_risk("delete_file", {"path": "/data/important.txt"})
    assert risk == RiskLevel.IRREVERSIBLE
```


## Constraints

- **Framework:** Pydantic AI only (Constitution Article I.C)
- **Tool Protocol:** All tools via MCP (Constitution Article I.E)
- **Testing:** 80%+ coverage with mock MCP servers
- **Type Safety:** All tool inputs/outputs must be Pydantic models
- **Observability:** Instrument all tool calls with OpenTelemetry


## Success Criteria

1. Agent successfully calls all 3 MCP tools in a test scenario
2. Tool Gap Detection correctly identifies missing capabilities
3. Risk categorization logic passes all test cases
4. Agent returns structured `AgentResponse` with confidence scores
5. Memory integration works (agent can store/retrieve documents)
6. All tests pass with >80% coverage
```

---

**Between-Specs Validation Workflow (Run After Spec 2):**

1. ✅ **Verification:**
   - **Unit Tests:** `pytest tests/test_researcher_agent.py --cov-fail-under=80`
   - **Manual Validation:**
     - Run standalone test script:
       ```
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
     - Verify agent actually called `web_search` tool (check logs)
     - Test Tool Gap Detection:
       ```
       result = await researcher_agent.run(
           "Retrieve my stock portfolio performance",
           deps=memory
       )
       # Should return ToolGapReport mentioning missing "portfolio_api" tool
       ```
     - Check Jaeger for tool call traces
2. ✅ **Commit:** `git add . && git commit -m "feat(phase1): researcher agent with MCP tools and gap detection"`
3. ✅ **Update Context:** Document which MCP servers are installed, any tool limitations

---

### Spec 3: The Orchestration Layer (Windmill + LangGraph)

**Goal:** Build the "Nervous System" that automates the "DailyTrendingResearch" flagship workflow.

**Command:**
```

spec-kit run specs/03-orchestration-workflow.md

```

**Spec Content:**
```


# Spec: DailyTrendingResearch Workflow (Windmill + LangGraph)

## Objective

Build the flagship "DailyTrendingResearch" workflow using Windmill for orchestration and LangGraph for the cyclical reasoning loop, as specified in Constitution Article I.B.

## Requirements

### 1. Windmill Flow (DAG Structure)

Create a Windmill workflow in `workflows/daily_trending_research.py`:

**Workflow Steps:**

1. **Input Validation** (Windmill step)
    - Accept: `topic` (string), `user_id` (string)
    - Validate: Not empty, reasonable length
    - Output: Validated parameters
2. **Deep Research Loop** (LangGraph inside Windmill step) ⚠️ **KEY REQUIREMENT**
    - This is where LangGraph operates as a library, not a separate service
    - Implements cyclical "Plan → Research → Critique → Refine" logic
    - See detailed specification below
3. **Human-in-the-Loop Approval Gate** (Windmill native approval)
    - Check risk level of actions taken during research
    - If any action is `REVERSIBLE_WITH_DELAY` or `IRREVERSIBLE`, pause for approval
    - Timeout: 5 minutes → escalate to manual review
4. **Report Generation** (Windmill step)
    - Format research findings into Markdown report
    - Store in `documents` table via MemoryManager
    - Generate summary statistics
5. **Notification** (Windmill step)
    - Log completion to OpenTelemetry
    - Return final report as workflow output

**Windmill Script Structure:**

```python
# workflows/daily_trending_research.py
import asyncio
from windmill import wmill
from agents.researcher import researcher_agent
from core.memory import MemoryManager
from workflows.research_graph import create_research_graph

async def main(topic: str, user_id: str):
    """
    Main Windmill workflow entry point
    Constitution compliance: Article I.B (Windmill as primary orchestrator)
    """
    # Step 1: Validation
    if not topic or len(topic) < 3:
        raise ValueError("Invalid topic")
    
    # Step 2: LangGraph Deep Research (see below)
    research_graph = create_research_graph(researcher_agent, MemoryManager())
    research_results = await research_graph.run_streaming(topic)
    
    # Step 3: Approval gate (if needed)
    if research_results.requires_approval:
        approval = await wmill.approval_request(
            description=f"Research actions for '{topic}' require review",
            approval_data=research_results.approval_requests
        )
        if not approval:
            raise Exception("User rejected research actions")
    
    # Step 4: Generate report
    report = await generate_markdown_report(research_results)
    
    # Step 5: Store and return
    memory = MemoryManager()
    await memory.store_document(report, {"type": "research_report", "topic": topic})
    
    return {
        "report": report,
        "summary": research_results.summary,
        "tool_calls": research_results.tool_calls_made
    }
```


### 2. LangGraph Deep Research Implementation

Create the stateful research graph in `workflows/research_graph.py`:

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List
from agents.researcher import researcher_agent
from models.common import AgentResponse

class ResearchState(TypedDict):
    topic: str
    plan: str
    sources: List[dict]
    critique: str
    refined_answer: str
    iteration: int
    max_iterations: Annotated[int, 5]  # Prevent infinite loops
    requires_approval: bool

def create_research_graph(agent, memory):
    """
    Constitution Article I.B: LangGraph handles cyclical reasoning
    This graph runs INSIDE a Windmill workflow step
    """
    workflow = StateGraph(ResearchState)
    
    # Node 1: Generate Research Plan
    async def plan_node(state: ResearchState):
        """Decide what to research"""
        result = await agent.run(
            f"Create a research plan for: {state['topic']}",
            deps=memory
        )
        return {"plan": result.data.answer}
    
    # Node 2: Execute Research
    async def research_node(state: ResearchState):
        """Use tools to gather information"""
        result = await agent.run(
            f"Research: {state['plan']}. Use web_search and memory.",
            deps=memory
        )
        return {
            "sources": result.data.tool_calls,
            "iteration": state["iteration"] + 1
        }
    
    # Node 3: Critique Results
    async def critique_node(state: ResearchState):
        """Evaluate quality of findings"""
        result = await agent.run(
            f"Critique these sources: {state['sources']}. Are they sufficient?",
            deps=memory
        )
        return {"critique": result.data.reasoning}
    
    # Node 4: Refine or Finish
    def should_refine(state: ResearchState) -> str:
        """Decide: refine or complete?"""
        if state["iteration"] >= state["max_iterations"]:
            return "finish"
        if "insufficient" in state["critique"].lower():
            return "refine"
        return "finish"
    
    async def refine_node(state: ResearchState):
        """Loop back with improved plan"""
        result = await agent.run(
            f"Refine research plan based on: {state['critique']}",
            deps=memory
        )
        return {"plan": result.data.answer}
    
    async def finish_node(state: ResearchState):
        """Generate final synthesis"""
        result = await agent.run(
            f"Synthesize final answer from: {state['sources']}",
            deps=memory
        )
        return {"refined_answer": result.data.answer}
    
    # Build the graph
    workflow.add_node("plan", plan_node)
    workflow.add_node("research", research_node)
    workflow.add_node("critique", critique_node)
    workflow.add_node("refine", refine_node)
    workflow.add_node("finish", finish_node)
    
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "research")
    workflow.add_edge("research", "critique")
    workflow.add_conditional_edges(
        "critique",
        should_refine,
        {
            "refine": "refine",
            "finish": "finish"
        }
    )
    workflow.add_edge("refine", "research")  # Loop back
    workflow.add_edge("finish", END)
    
    return workflow.compile()
    
    # Streaming configuration (for UI real-time display)
    async def run_streaming(self, topic: str):
        """Stream intermediate node outputs to Windmill logs"""
        state = {"topic": topic, "iteration": 0, "max_iterations": 5}
        
        async for output in self.stream(state):
            # Log each node's output for UI consumption
            print(f"🔍 Node: {output['node_name']}")
            print(f"📊 Output: {output['data']}")
            
        return output['data']
```

**Critical Requirement:** LangGraph must be **imported as a library** and invoked within the Windmill Python script. It is not a separate microservice.

### 3. Execution Isolation \& Security

Implement subprocess isolation (Constitution Article II.F):

```python
# core/isolation.py
import subprocess
import json
from typing import Any

async def execute_in_sandbox(agent_func, args: dict) -> Any:
    """
    Execute agent in isolated subprocess with resource limits
    Constitution Article II.F: Isolation Safety Boundaries
    """
    # Serialize agent execution
    script = f"""
import asyncio
from agents.researcher import researcher_agent
from core.memory import MemoryManager

async def main():
    result = await researcher_agent.run("{args['query']}", deps=MemoryManager())
    print(result.model_dump_json())

asyncio.run(main())
"""
    
    # Run in subprocess with limits
    result = subprocess.run(
        ["python", "-c", script],
        capture_output=True,
        timeout=60,  # 1 minute limit
        text=True
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Agent execution failed: {result.stderr}")
    
    return json.loads(result.stdout)
```

**Apply to Windmill:** Configure Windmill's per-workflow resource limits (CPU/memory) in the workflow metadata.

### 4. Windmill Deployment Configuration

Create `wmill.yaml`:

```yaml
# wmill.yaml
type: script
language: python
path: u/admin/daily_trending_research

summary: "Daily Trending Research Workflow"
description: "Phase 1 flagship workflow: research a topic using cyclical LangGraph reasoning"

schema:
  $schema: "https://json-schema.org/draft-07/schema"
  type: object
  properties:
    topic:
      type: string
      description: "Research topic"
    user_id:
      type: string
      description: "User requesting research"
  required:
    - topic
    - user_id

# Resource limits (Constitution Article II.F)
resources:
  cpu_limit: "1000m"  # 1 CPU core
  memory_limit: "2Gi"
  timeout: "300s"  # 5 minutes
```


### 5. Integration with Previous Specs

- Import `ResearcherAgent` from Spec 2
- Use `MemoryManager` from Spec 1
- Emit OpenTelemetry traces for every graph node execution
- Store final report using `MemoryManager.store_document()`


## Constraints

- **Primary Orchestrator:** Windmill (Constitution Article I.B)
- **Complex Reasoning:** LangGraph as library, not service
- **Isolation:** Subprocess execution for security
- **Observability:** Trace every LangGraph node execution
- **Approval Gates:** Windmill's native approval for `REVERSIBLE_WITH_DELAY` actions


## Success Criteria

1. Workflow can be triggered manually in Windmill UI
2. LangGraph executes the "Plan → Research → Critique → Refine" loop
3. Intermediate node outputs appear in Windmill logs (streaming)
4. Approval gate pauses workflow when required
5. Final Markdown report is stored in PostgreSQL `documents` table
6. Complete OpenTelemetry trace spans entire workflow (UI → Windmill → LangGraph → Agent → MCP → DB)
```

---

**Between-Specs Validation Workflow (Run After Spec 3):**

1. ✅ **Verification:**
   - **Deploy to Windmill:**
     ```
     wmill sync push workflows/daily_trending_research.py
     ```
   - **Trigger Workflow:**
     - Open Windmill UI: `http://localhost:8000`
     - Navigate to the workflow
     - Input: `{"topic": "Latest developments in quantum computing", "user_id": "test_user"}`
     - Click "Run"
   - **Check Logs:** Verify you see LangGraph node executions:
     ```
     🔍 Node: plan
     📊 Output: Research plan created...
     🔍 Node: research
     📊 Output: Found 12 sources...
     🔍 Node: critique
     📊 Output: Sources are sufficient...
     🔍 Node: finish
     📊 Output: Final synthesis complete
     ```
   - **Verify Database:**
     ```
     SELECT * FROM documents WHERE metadata->>'type' = 'research_report';
     ```
   - **Jaeger Trace:** Open `http://localhost:16686`, search for the workflow execution, verify spans for:
     - Windmill workflow start
     - LangGraph state transitions
     - Agent tool calls (web_search)
     - Database writes
2. ✅ **Commit:** `git add . && git commit -m "feat(phase1): windmill+langgraph orchestration with DailyTrendingResearch workflow"`
3. ✅ **Update Context:** Document Windmill deployment process, any workflow customizations

---

### Spec 4: The User Interface (Vertical Slice Completion)

**Goal:** The "Face" of the system. A chat UI to trigger the workflow and view results with real-time streaming.

**Command:**
```

spec-kit run specs/04-ui-interface.md

```

**Spec Content:**
```


# Spec: Simple Chat UI with Real-Time Streaming (Streamlit)

## Objective

Build the user-facing interface that completes the Phase 1 Vertical Slice: User → UI → Workflow → Agent → Memory.

## Requirements

### 1. Streamlit Chat Interface

Create `ui/app.py`:

```python
import streamlit as st
import httpx
import asyncio
from datetime import datetime

st.set_page_config(
    page_title="PAIAS - Personal AI Assistant",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Personal AI Assistant - Phase 1")
st.caption("Powered by Windmill + LangGraph + Pydantic AI")

# Session state for conversation history
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Sidebar: History from PostgreSQL
with st.sidebar:
    st.header("📚 Research History")
    
    # Query past reports from MemoryManager
    @st.cache_data(ttl=300)
    def load_history():
        # Call API endpoint to fetch past reports
        response = httpx.get("http://localhost:8000/api/reports/history")
        return response.json()
    
    history = load_history()
    for report in history:
        if st.button(f"📄 {report['topic']}", key=report['id']):
            st.session_state.selected_report = report

# Main chat interface
chat_container = st.container()

with chat_container:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
            # Show metadata in expander
            if "metadata" in msg:
                with st.expander("🔍 View Thought Process"):
                    st.json(msg["metadata"])

# Input box
if prompt := st.chat_input("Enter research topic..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Trigger workflow and stream response
    with st.chat_message("assistant"):
        response_container = st.empty()
        metadata_container = st.expander("🔍 View Thought Process")
        
        # Real-time streaming from Windmill
        await stream_workflow_execution(prompt, response_container, metadata_container)
```


### 2. Real-Time Streaming from Windmill

Implement WebSocket or Server-Sent Events (SSE) connection:

```python
async def stream_workflow_execution(topic: str, response_container, metadata_container):
    """
    Stream workflow execution updates in real-time
    Constitution success metric: Token-by-token streaming + live tool feedback
    """
    WINDMILL_API = "http://localhost:8000/api"
    
    # Trigger workflow
    async with httpx.AsyncClient() as client:
        # Start workflow job
        job_response = await client.post(
            f"{WINDMILL_API}/w/admin/jobs/run/u/admin/daily_trending_research",
            json={"topic": topic, "user_id": st.session_state.session_id}
        )
        job_id = job_response.json()["job_id"]
        
        # Stream logs and results
        full_response = ""
        metadata = {"tool_calls": [], "confidence": None}
        
        async with client.stream("GET", f"{WINDMILL_API}/jobs/{job_id}/stream") as stream:
            async for line in stream.aiter_lines():
                if not line:
                    continue
                
                # Parse streaming events
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    
                    # Handle different event types
                    if event["type"] == "log":
                        # Live tool execution feedback
                        if "🔍 Node:" in event["message"]:
                            metadata_container.write(event["message"])
                        
                    elif event["type"] == "progress":
                        # Show progress (e.g., "Searching... Found 45 sources")
                        with response_container:
                            st.info(event["message"])
                    
                    elif event["type"] == "token":
                        # Token-by-token streaming of final answer
                        full_response += event["token"]
                        response_container.markdown(full_response + "▌")
                    
                    elif event["type"] == "complete":
                        # Final result
                        result = event["result"]
                        response_container.markdown(result["report"])
                        
                        metadata["tool_calls"] = result["tool_calls"]
                        metadata["confidence"] = result.get("confidence", 0.0)
        
        # Store in session
        st.session_state.messages.append({
            "role": "assistant",
            "content": full_response,
            "metadata": metadata
        })
```

**Fallback (if Windmill streaming is complex):** Poll for job status every 2 seconds and display incremental updates.

### 3. Confidence Meter Display

Add visual confidence indicator:

```python
def display_confidence_meter(confidence: float):
    """Visual confidence score (Constitution success metric)"""
    color = "red" if confidence < 0.5 else "orange" if confidence < 0.85 else "green"
    
    st.markdown(f"""
    <div style="padding: 10px; background-color: {color}; border-radius: 5px;">
        <strong>Confidence:</strong> {confidence:.0%}
    </div>
    """, unsafe_allow_html=True)
```

Call this in the metadata expander after workflow completes.

### 4. History Sidebar (Reading from PostgreSQL)

Implement API endpoint to fetch past reports:

```python
# api/reports.py (FastAPI endpoint)
from fastapi import FastAPI, Depends
from core.memory import MemoryManager

app = FastAPI()

@app.get("/api/reports/history")
async def get_history(memory: MemoryManager = Depends()):
    """Fetch past research reports from documents table"""
    reports = await memory.temporal_query(
        date_range=(datetime.now() - timedelta(days=30), datetime.now()),
        filters={"metadata->>'type'": "research_report"}
    )
    return [
        {
            "id": str(r.id),
            "topic": r.metadata.get("topic", "Unknown"),
            "created_at": r.created_at.isoformat(),
            "preview": r.content[:200] + "..."
        }
        for r in reports
    ]
```


### 5. Docker Compose Update

Add Streamlit and FastAPI to `docker-compose.yml`:

```yaml
services:
  # ... existing postgres, jaeger, windmill ...
  
  api:
    build: ./api
    ports:
      - "8080:8080"
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:password@postgres:5432/paias
    depends_on:
      - postgres
  
  ui:
    build: ./ui
    ports:
      - "8501:8501"
    environment:
      WINDMILL_API: http://windmill:8000
      API_URL: http://api:8080
    depends_on:
      - api
      - windmill
```


## Constraints

- **Framework:** Streamlit (Constitution Article I.F)
- **Streaming:** Real-time updates (Constitution success metric: "token-by-token streaming")
- **History:** Pull from PostgreSQL via MemoryManager
- **Integration:** Trigger Windmill workflows via API/webhook


## Success Criteria

1. User can type a research topic in the chat interface
2. Workflow triggers in Windmill
3. UI displays live progress updates:
    - "🔍 Node: plan → Planning research..."
    - "🔍 Node: research → Searching... Found 45 sources"
    - "🔍 Node: critique → Evaluating sources..."
4. Final answer streams token-by-token (not waiting for full completion)
5. "View Thought Process" expander shows:
    - Tools called
    - Confidence score
    - Reasoning chain
6. Confidence meter displays visually (red/orange/green)
7. History sidebar shows past reports from last 30 days
8. Full vertical slice works: Type "Latest AI trends" → See live research → Get Markdown report

***

**Final Validation (Run After Spec 4):**

1. ✅ **End-to-End Test:**
    - Start all services: `docker-compose up -d`
    - Open UI: `http://localhost:8501`
    - Input: "Summarize recent breakthroughs in fusion energy"
    - **Verify:**
        - Windmill job starts (check Windmill UI)
        - Streamlit shows live progress updates
        - Final answer appears token-by-token
        - Thought process shows tool calls
        - Confidence meter displays
        - Report appears in history sidebar after refresh
2. ✅ **Jaeger Verification:**
    - Open `http://localhost:16686`
    - Search for the research session
    - Verify complete trace: UI → API → Windmill → LangGraph → Agent → MCP → PostgreSQL
3. ✅ **Success Metrics Check (Constitution Phase 1 requirements):**
    - ✅ Agent Decision Approval Rate: Track how many actions required approval
    - ✅ Tool Execution Success Rate: Check MCP tool success logs
    - ✅ Response Latency P50: <30s simple, <60s complex (measure via Jaeger)
    - ✅ Observability Completeness: 100% trace coverage verified
4. ✅ **Commit:** `git add . && git commit -m "feat(phase1): complete vertical slice with streaming UI"`
5. ✅ **Update Context:** Phase 1 COMPLETE. Document final architecture diagram, known limitations, Phase 2 readiness.

***

## Phase 1 Completion Checklist

**Before declaring Phase 1 complete, verify all Constitutional requirements:**

- [x] **Article I.A:** Python 3.11+ with async throughout
- [x] **Article I.B:** Windmill (DAG) + LangGraph (loops) demonstrated
- [x] **Article I.C:** Pydantic AI agents operational
- [x] **Article I.D:** PostgreSQL + pgvector for memory
- [x] **Article I.E:** All tools via MCP (web_search, filesystem, time)
- [x] **Article I.F:** Streamlit UI with streaming
- [x] **Article II.C:** Human-in-the-Loop approval gates functional
- [x] **Article II.D:** OpenTelemetry instrumented (100% trace coverage)
- [x] **Article II.G:** Tool Gap Detection implemented and tested
- [x] **Article III.A:** 80%+ test coverage verified
- [x] **Success Metric 1:** Agent Decision Approval Rate ≥80%
- [x] **Success Metric 2:** Tool Execution Success Rate ≥90%
- [x] **Success Metric 3:** Workflow Completion Rate ≥95%
- [x] **Success Metric 4:** User Task Completion Rate ≥85%
- [x] **Success Metric 5:** Response Latency P50 <30s simple, <60s complex
- [x] **Success Metric 6:** Real-time streaming functional (token-by-token, live tool feedback)

***

## Appendix: The "Between-Specs" Workflow (Master Checklist)

**Use this after EVERY spec completion:**

1. ✅ **Generate Plan:** `spec-kit plan specs/XX-name.md`
2. ✅ **Generate Tasks:** `spec-kit tasks specs/XX-name.md`
3. ✅ **Implement \& Test:** Complete all tasks with >80% coverage
4. ✅ **Manual Validation:**
    - Run the component in isolation
    - Verify against Constitution requirements
    - Check Jaeger for traces
5. ✅ **Commit Code:** `git add . && git commit -m "feat(phase1): [description]"`
6. ✅ **Update Context:** Update `project-context.md` with any architectural decisions or deviations

**Only after all 6 steps pass do you proceed to the next spec.**

***

## Glossary

- **Vertical Slice:** Complete end-to-end system (UI → Workflow → Agent → Memory) delivering a functional feature
- **MCP (Model Context Protocol):** Universal standard for tool discovery and execution
- **Risk Level:** Action categorization (reversible/reversible-with-delay/irreversible) for human-in-the-loop policy
- **Tool Gap Detection:** Agent capability to identify missing tools and emit structured requirements
- **OpenTelemetry:** Distributed tracing standard for observability across all layers

***

**Document Status:** Ready for Implementation
**Next Action:** Run `spec-kit run specs/01-foundation-memory.md`

```

This complete execution plan incorporates all your constitutional requirements, the flagship DailyTrendingResearch workflow, proper abstraction layers, risk-based escalation, and detailed validation workflows between each spec. It's ready to execute.```

