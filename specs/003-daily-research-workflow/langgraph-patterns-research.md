# LangGraph State Machine Implementation Patterns: Research Workflow

**Research Date**: 2025-12-24
**Branch**: `003-daily-research-workflow`
**Purpose**: Concrete code patterns for implementing a cyclical research workflow with LangGraph

## Executive Summary

This document provides production-ready implementation patterns for building a cyclical research workflow using LangGraph. The workflow implements Plan → Research → Critique → Refine → Finish nodes with:
- Type-safe state management using Pydantic models
- Conditional routing based on quality and iteration limits
- Hard stop at 5 iterations maximum
- Integration with existing Pydantic AI agents and MCP tools
- Streaming execution and OpenTelemetry observability

All patterns are compatible with the project's existing architecture (Python 3.11+, Pydantic AI, MCP tools, unified telemetry).

---

## 1. State Management with Pydantic Models

LangGraph supports Pydantic models for type-safe state management, aligning perfectly with the project's existing patterns.

### ResearchState Model

```python
"""Research workflow state management using Pydantic."""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class SourceReference(BaseModel):
    """A single source citation."""

    title: str = Field(..., description="Source title")
    url: str = Field(..., description="Source URL")
    snippet: str = Field(..., description="Relevant excerpt", max_length=1000)
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)


class ResearchState(BaseModel):
    """State for the research workflow graph.

    This state is passed between all nodes and accumulates
    findings across iterations.
    """

    # Input (immutable)
    topic: str = Field(..., description="Research topic from user", min_length=1, max_length=500)
    user_id: str = Field(..., description="User ID for memory storage")

    # Workflow state (accumulated)
    plan: Optional[str] = Field(None, description="Research plan from Plan node")
    sources: List[SourceReference] = Field(
        default_factory=list,
        description="Accumulated sources from Research node"
    )
    critique: Optional[str] = Field(
        None,
        description="Quality assessment from Critique node"
    )
    refined_answer: Optional[str] = Field(
        None,
        description="Current best answer from Refine node"
    )

    # Control flow
    iteration_count: int = Field(0, ge=0, description="Current iteration number (0-based)")
    status: Literal["planning", "researching", "critiquing", "refining", "finished"] = Field(
        "planning",
        description="Current workflow stage"
    )
    quality_score: float = Field(0.0, ge=0.0, le=1.0, description="Quality assessment score")

    # Configuration (immutable)
    max_iterations: int = Field(5, ge=1, le=10, description="Maximum allowed iterations")
    quality_threshold: float = Field(0.8, ge=0.0, le=1.0, description="Minimum quality to finish")

    class Config:
        """Pydantic config for state model."""

        # Allow arbitrary types (needed for datetime)
        arbitrary_types_allowed = True

        # Example for documentation
        json_schema_extra = {
            "example": {
                "topic": "AI governance trends 2025",
                "user_id": "user-123",
                "plan": "1. Search regulatory frameworks 2. Analyze enforcement 3. Summarize trends",
                "sources": [
                    {
                        "title": "EU AI Act 2025",
                        "url": "https://...",
                        "snippet": "The AI Act establishes...",
                        "retrieved_at": "2025-12-24T10:30:00Z"
                    }
                ],
                "iteration_count": 2,
                "status": "refining",
                "quality_score": 0.75,
                "max_iterations": 5,
                "quality_threshold": 0.8
            }
        }
```

**Key Features**:
- **Type Safety**: Pydantic validation ensures correct data types
- **Default Values**: Control flow fields have sensible defaults
- **Literal Types**: `status` field uses Literal for compile-time checking
- **Constraints**: `max_length`, `ge`, `le` enforce business rules
- **Accumulator Pattern**: `sources` list grows across iterations
- **Immutability Markers**: Comments indicate which fields shouldn't change

### Alternative: TypedDict Approach

```python
"""Alternative state management using TypedDict (more flexible, less validation)."""

from typing import TypedDict, List, Optional, Literal


class SourceReference(TypedDict):
    title: str
    url: str
    snippet: str
    retrieved_at: str  # ISO format datetime


class ResearchState(TypedDict, total=False):
    """TypedDict-based state (less validation, more flexibility)."""

    # Required fields
    topic: str
    user_id: str
    iteration_count: int
    status: Literal["planning", "researching", "critiquing", "refining", "finished"]

    # Optional fields
    plan: Optional[str]
    sources: List[SourceReference]
    critique: Optional[str]
    refined_answer: Optional[str]
    quality_score: float
    max_iterations: int
    quality_threshold: float
```

**Recommendation**: Use **Pydantic** model for:
- Runtime validation
- Consistent error messages
- Integration with existing project patterns (AgentResponse, etc.)

---

## 2. Graph Definition with Cyclical Structure

LangGraph uses `StateGraph` to define nodes and edges. Conditional edges enable dynamic routing.

### Complete Graph Construction

```python
"""LangGraph state machine for cyclical research workflow."""

from typing import Literal
from langgraph.graph import StateGraph, END
from src.models.research_state import ResearchState


def create_research_graph() -> StateGraph:
    """Create the research workflow graph with Plan→Research→Critique→Refine→Finish.

    Graph structure:
    - Entry: Plan
    - Linear: Plan → Research → Critique
    - Conditional: Critique → (Refine OR Finish)
    - Loop: Refine → Research
    - Exit: Finish → END

    Returns:
        Compiled StateGraph ready for execution
    """

    # Initialize graph with ResearchState type
    graph = StateGraph(ResearchState)

    # Add nodes (implementation functions defined in nodes/)
    graph.add_node("plan", plan_node)
    graph.add_node("research", research_node)
    graph.add_node("critique", critique_node)
    graph.add_node("refine", refine_node)
    graph.add_node("finish", finish_node)

    # Define linear edges
    graph.add_edge("plan", "research")
    graph.add_edge("research", "critique")

    # Conditional routing: Critique → Refine OR Critique → Finish
    graph.add_conditional_edges(
        "critique",                     # Source node
        should_continue_research,       # Routing function
        {
            "refine": "refine",        # Continue iterating
            "finish": "finish"         # Quality met or max iterations
        }
    )

    # Cycle back: Refine → Research for next iteration
    graph.add_edge("refine", "research")

    # Terminal edge: Finish → END
    graph.add_edge("finish", END)

    # Set entry point
    graph.set_entry_point("plan")

    # Compile graph (validates structure, optimizes execution)
    return graph.compile()


def should_continue_research(state: ResearchState) -> Literal["refine", "finish"]:
    """Conditional routing function for Critique node.

    Decides whether to continue iterating (refine) or finalize (finish).

    Decision logic (priority order):
    1. Hard stop at max_iterations (FR-005: non-negotiable)
    2. Quality threshold met → finish
    3. Otherwise → continue refining

    Args:
        state: Current ResearchState

    Returns:
        "refine" if more iterations needed, "finish" if done
    """

    # Priority 1: Hard stop at max iterations (per FR-005)
    if state.iteration_count >= state.max_iterations:
        return "finish"

    # Priority 2: Check quality threshold
    if state.quality_score >= state.quality_threshold:
        return "finish"

    # Priority 3: Continue refining
    return "refine"
```

### Graph Visualization

```
┌──────┐
│ Plan │ (Entry point)
└───┬──┘
    │
    ▼
┌──────────┐
│ Research │◄─────┐ (Loop back from Refine)
└────┬─────┘      │
     │            │
     ▼            │
┌──────────┐      │
│ Critique │      │
└────┬─────┘      │
     │            │
     ▼            │
  [Decision]      │
     │            │
     ├──(quality met OR max iter)──►┌────────┐
     │                               │ Finish │──►END
     │                               └────────┘
     │
     └──(needs work)────────────────►┌────────┐
                                     │ Refine │
                                     └────┬───┘
                                          │
                                          └────┘ (cycle back to Research)
```

### Key Implementation Details

1. **StateGraph(ResearchState)**: Binds Pydantic model to graph for type checking
2. **add_conditional_edges**: Enables dynamic routing based on state
3. **should_continue_research**: Encapsulates decision logic (testable!)
4. **compile()**: Validates graph structure, prevents invalid topologies
5. **END**: Special constant indicating workflow termination

---

## 3. Node Implementation Patterns

Each node is an async function that receives state and returns updated state.

### Plan Node

```python
"""Plan node: Generate research strategy."""

from src.core.llm import get_azure_model, parse_agent_result
from src.core.telemetry import trace_agent_operation
from pydantic_ai import Agent
import logging

logger = logging.getLogger(__name__)


async def plan_node(state: ResearchState) -> ResearchState:
    """Generate a research plan based on the topic.

    Uses LLM to create a structured research strategy.

    Args:
        state: Current ResearchState

    Returns:
        Updated state with plan field populated and status="researching"
    """

    logger.info("📋 [PLAN] Generating research plan for: %s", state.topic)

    # Create lightweight planning agent (no tools needed)
    model = get_azure_model()
    planner_agent = Agent[None, str](
        model=model,
        output_type=str,
        system_prompt="""You are a research planning assistant.

Given a research topic, create a focused 3-step research plan:
1. Primary information sources to search
2. Key questions to answer
3. Expected deliverables

Be specific and actionable. Keep plan under 300 words."""
    )

    # Generate plan
    prompt = f"Create a research plan for topic: {state.topic}"
    result = await planner_agent.run(prompt)
    plan = parse_agent_result(result)

    # Update state
    state.plan = plan
    state.status = "researching"

    logger.info("✅ [PLAN] Plan created (%d chars)", len(plan))
    return state
```

### Research Node

```python
"""Research node: Execute searches and gather sources."""

from src.agents.researcher import setup_researcher_agent, run_agent_with_tracing
from src.core.memory import MemoryManager
from src.models.agent_response import AgentResponse
from typing import List
import logging

logger = logging.getLogger(__name__)


async def research_node(state: ResearchState, memory_manager: MemoryManager) -> ResearchState:
    """Execute research using ResearcherAgent with MCP tools.

    Integrates existing ResearcherAgent from Spec 002 for web search
    and source gathering.

    Args:
        state: Current ResearchState
        memory_manager: MemoryManager dependency for agent

    Returns:
        Updated state with new sources appended, iteration_count incremented
    """

    logger.info(
        "🔬 [RESEARCH] Starting iteration %d/%d",
        state.iteration_count + 1,
        state.max_iterations
    )

    # Setup ResearcherAgent with MCP tools
    agent, mcp_session = await setup_researcher_agent(memory_manager)

    try:
        # Construct research task from plan and topic
        task = f"""Research topic: {state.topic}

Plan: {state.plan}

Current iteration: {state.iteration_count + 1}/{state.max_iterations}

Find 3-5 high-quality sources. Include URLs, titles, and relevant excerpts."""

        # Execute agent with tracing (OpenTelemetry spans auto-created)
        response: AgentResponse = await run_agent_with_tracing(
            agent=agent,
            task=task,
            deps=memory_manager,
            mcp_session=mcp_session
        )

        # Parse sources from agent response
        new_sources = _extract_sources_from_response(response)

        # Append to state (accumulator pattern)
        state.sources.extend(new_sources)
        state.iteration_count += 1
        state.status = "critiquing"

        logger.info(
            "✅ [RESEARCH] Found %d sources (total: %d)",
            len(new_sources),
            len(state.sources)
        )

        return state

    finally:
        # Cleanup MCP session
        if hasattr(mcp_session, "_close_cm"):
            await mcp_session._close_cm.__aexit__(None, None, None)


def _extract_sources_from_response(response: AgentResponse) -> List[SourceReference]:
    """Parse SourceReference objects from agent response.

    Extracts source metadata from tool_calls (specifically web_search results).

    Args:
        response: AgentResponse from ResearcherAgent

    Returns:
        List of SourceReference objects
    """
    from datetime import datetime

    sources = []

    # Extract sources from tool_calls (if web_search was used)
    for tool_call in response.tool_calls:
        if tool_call.tool_name == "search" and tool_call.status.value == "success":
            if isinstance(tool_call.result, list):
                for item in tool_call.result[:5]:  # Limit to 5 per tool call
                    if isinstance(item, dict):
                        sources.append(SourceReference(
                            title=item.get("title", "Untitled"),
                            url=item.get("url", ""),
                            snippet=item.get("snippet", "")[:500],  # Truncate
                            retrieved_at=datetime.utcnow()
                        ))

    return sources
```

### Critique Node

```python
"""Critique node: Assess research quality and completeness."""

from src.core.llm import get_azure_model, parse_agent_result
from pydantic_ai import Agent
from pydantic import BaseModel, Field
from typing import List
import logging

logger = logging.getLogger(__name__)


class CritiqueResult(BaseModel):
    """Structured critique assessment."""

    quality_score: float = Field(..., ge=0.0, le=1.0, description="Overall quality score")
    critique: str = Field(..., description="Detailed quality assessment")
    gaps: List[str] = Field(default_factory=list, description="Identified knowledge gaps")


async def critique_node(state: ResearchState) -> ResearchState:
    """Assess quality of current research findings.

    Uses LLM to evaluate completeness, source quality, and coverage.

    Args:
        state: Current ResearchState

    Returns:
        Updated state with quality_score and critique populated
    """

    logger.info(
        "🔍 [CRITIQUE] Evaluating quality at iteration %d",
        state.iteration_count
    )

    model = get_azure_model()
    critic_agent = Agent[None, CritiqueResult](
        model=model,
        output_type=CritiqueResult,
        system_prompt="""You are a research quality critic.

Evaluate research findings on:
1. Source diversity and credibility (30%)
2. Topic coverage and completeness (40%)
3. Answer clarity and structure (30%)

Provide:
- quality_score: 0.0 (poor) to 1.0 (excellent)
- critique: Specific strengths and weaknesses
- gaps: Missing information or areas needing improvement"""
    )

    # Prepare critique prompt
    sources_summary = "\n".join([
        f"- {s.title} ({s.url}): {s.snippet[:100]}..."
        for s in state.sources[-10:]  # Last 10 sources to avoid context overflow
    ])

    prompt = f"""Evaluate research quality for topic: {state.topic}

Sources found ({len(state.sources)} total):
{sources_summary}

Current answer: {state.refined_answer or "None yet"}

Iteration {state.iteration_count}/{state.max_iterations}"""

    # Get critique
    result = await critic_agent.run(prompt)
    critique_result: CritiqueResult = parse_agent_result(result)

    # Update state
    state.quality_score = critique_result.quality_score
    state.critique = critique_result.critique
    state.status = "critiquing"

    logger.info(
        "✅ [CRITIQUE] Quality score: %.2f | Gaps: %d",
        critique_result.quality_score,
        len(critique_result.gaps)
    )

    return state
```

### Refine Node

```python
"""Refine node: Improve answer based on critique."""

from src.core.llm import get_azure_model, parse_agent_result
from pydantic_ai import Agent
import logging

logger = logging.getLogger(__name__)


async def refine_node(state: ResearchState) -> ResearchState:
    """Refine the research answer based on critique feedback.

    Uses LLM to synthesize findings and address gaps.

    Args:
        state: Current ResearchState

    Returns:
        Updated state with refined_answer improved, status="researching"
    """

    logger.info("✨ [REFINE] Improving answer based on critique")

    model = get_azure_model()
    refiner_agent = Agent[None, str](
        model=model,
        output_type=str,
        system_prompt="""You are a research synthesizer.

Given sources and critique feedback, improve the research answer by:
1. Addressing identified gaps
2. Incorporating diverse sources
3. Structuring findings clearly

Output a comprehensive answer (500-1000 words) with inline citations."""
    )

    # Build context
    sources_text = "\n\n".join([
        f"[{i+1}] {s.title} ({s.url})\n{s.snippet}"
        for i, s in enumerate(state.sources)
    ])

    prompt = f"""Refine research answer for: {state.topic}

Sources:
{sources_text}

Previous answer: {state.refined_answer or "None"}

Critique: {state.critique}

Create an improved answer addressing the critique."""

    # Generate refined answer
    result = await refiner_agent.run(prompt)
    refined_answer = parse_agent_result(result)

    # Update state
    state.refined_answer = refined_answer
    state.status = "researching"  # Loop back to research

    logger.info("✅ [REFINE] Answer refined (%d chars)", len(refined_answer))

    return state
```

### Finish Node

```python
"""Finish node: Finalize and format the research report."""

from src.models.research_report import ResearchReport
from src.core.memory import MemoryManager
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


async def finish_node(state: ResearchState, memory_manager: MemoryManager) -> ResearchState:
    """Finalize research and store results.

    Creates markdown report and persists to memory (per FR-009).

    Args:
        state: Current ResearchState
        memory_manager: MemoryManager for storage

    Returns:
        Updated state with status="finished"
    """

    logger.info("🎯 [FINISH] Finalizing research workflow")

    # Format final report
    from src.workflows.report_formatter import format_research_report

    report_markdown = format_research_report(state)

    # Store in memory (per FR-009)
    metadata = {
        "topic": state.topic,
        "user_id": state.user_id,
        "iterations": state.iteration_count,
        "quality_score": state.quality_score,
        "source_count": len(state.sources),
        "timestamp": datetime.utcnow().isoformat()
    }

    await memory_manager.store_document(
        content=report_markdown,
        metadata=metadata
    )

    # Update state
    state.status = "finished"

    logger.info(
        "✅ [FINISH] Research complete | Quality: %.2f | Sources: %d",
        state.quality_score,
        len(state.sources)
    )

    return state
```

---

## 4. Iteration Counting and Hard Limits

Iteration control is critical for preventing infinite loops.

### Iteration Flow

```python
"""Iteration counting implementation."""

def should_continue_research(state: ResearchState) -> Literal["refine", "finish"]:
    """Enforce max iterations and quality threshold.

    This function is called by the conditional edge after Critique node.

    Decision logic (priority order):
    1. Hard stop at max_iterations (FR-005: non-negotiable)
    2. Quality threshold met → finish
    3. Otherwise → refine and continue

    Args:
        state: Current ResearchState with iteration_count and quality_score

    Returns:
        "finish" or "refine"
    """

    import logging
    logger = logging.getLogger(__name__)

    # Priority 1: Hard iteration limit (non-negotiable per FR-005)
    if state.iteration_count >= state.max_iterations:
        logger.warning(
            "⚠️ Research workflow reached max iterations (%d). "
            "Finalizing with quality_score=%.2f (threshold=%.2f)",
            state.max_iterations,
            state.quality_score,
            state.quality_threshold
        )
        return "finish"

    # Priority 2: Quality threshold met
    if state.quality_score >= state.quality_threshold:
        logger.info(
            "✅ Quality threshold met (%.2f >= %.2f) at iteration %d",
            state.quality_score,
            state.quality_threshold,
            state.iteration_count
        )
        return "finish"

    # Priority 3: Continue refining
    logger.info(
        "🔄 Continuing refinement (iteration %d/%d, quality %.2f/%.2f)",
        state.iteration_count,
        state.max_iterations,
        state.quality_score,
        state.quality_threshold
    )
    return "refine"
```

### Iteration Tracking Flow

```
Iteration 0:
- Plan node: Sets up strategy (no increment)
- Research node: Gathers sources, increments iteration_count to 1
- Critique node: Evaluates quality
- Conditional: iteration_count=1 < max_iterations=5 → refine
- Refine node: Improves answer

Iteration 1:
- Research node: Gathers more sources, increments iteration_count to 2
- Critique node: Evaluates quality
- Conditional: iteration_count=2 < max_iterations=5 → refine OR finish
...

Iteration 5:
- Research node: Final sources, increments iteration_count to 5
- Critique node: Final evaluation
- Conditional: iteration_count=5 >= max_iterations=5 → finish (hard stop)
- Finish node: Finalize report
```

**Guarantees**:
- Maximum research cycles: `max_iterations` (default 5)
- No infinite loops (hard stop enforced)
- `iteration_count` is monotonically increasing (0-based)

---

## 5. MCP Tool Integration Within Nodes

LangGraph nodes can call external tools via existing ResearcherAgent.

### Integration Pattern

```python
"""MCP tool integration within LangGraph nodes."""

from src.agents.researcher import setup_researcher_agent, run_agent_with_tracing
from src.core.memory import MemoryManager


async def research_node(state: ResearchState, memory_manager: MemoryManager) -> ResearchState:
    """Research node with MCP tool integration.

    Uses existing ResearcherAgent which already integrates MCP tools
    (Spec 002: web_search, search_memory, store_memory, etc.)

    Args:
        state: Current ResearchState
        memory_manager: MemoryManager dependency

    Returns:
        Updated state with sources and incremented iteration_count
    """

    # Use existing ResearcherAgent setup (already has MCP tools)
    agent, mcp_session = await setup_researcher_agent(memory_manager)

    try:
        task = f"Research: {state.topic}\nPlan: {state.plan}"

        # run_agent_with_tracing creates OpenTelemetry spans automatically
        response = await run_agent_with_tracing(
            agent=agent,
            task=task,
            deps=memory_manager,
            mcp_session=mcp_session
        )

        # Process response (extract sources, etc.)
        new_sources = _extract_sources_from_response(response)
        state.sources.extend(new_sources)
        state.iteration_count += 1
        state.status = "critiquing"

        return state

    finally:
        # Cleanup MCP session
        if hasattr(mcp_session, "_close_cm"):
            await mcp_session._close_cm.__aexit__(None, None, None)
```

**Key Integration Points**:
- `setup_researcher_agent()` returns configured agent + MCP session
- `run_agent_with_tracing()` provides OpenTelemetry spans
- Tool calls are logged in `AgentResponse.tool_calls`
- Session cleanup in `finally` block

**Advantages**:
- Reuses existing agent infrastructure (Spec 002)
- No duplicate MCP setup code
- Automatic tool gap detection
- Risk assessment integration
- Comprehensive telemetry

---

## 6. Streaming and Observability

LangGraph supports streaming execution for real-time updates.

### Streaming Execution

```python
"""Streaming execution for real-time progress updates."""

from typing import AsyncIterator
import logging

logger = logging.getLogger(__name__)


async def execute_research_workflow_streaming(
    topic: str,
    user_id: str,
    memory_manager: MemoryManager
) -> AsyncIterator[ResearchState]:
    """Execute research workflow with streaming state updates.

    Yields state after each node execution for real-time UI updates.

    Args:
        topic: Research topic
        user_id: User identifier
        memory_manager: MemoryManager dependency

    Yields:
        ResearchState after each node completes
    """

    # Create graph
    graph = create_research_graph()

    # Initialize state
    initial_state = ResearchState(
        topic=topic,
        user_id=user_id,
        iteration_count=0,
        status="planning"
    )

    # Stream execution
    async for event in graph.astream(initial_state):
        # event is dict: {node_name: updated_state}
        for node_name, state in event.items():
            # Yield state for UI update
            yield state

            # Log progress
            logger.info(
                "📊 [WORKFLOW] Node '%s' completed | Iteration %d/%d | Quality %.2f",
                node_name,
                state.iteration_count,
                state.max_iterations,
                state.quality_score
            )


# Usage example
async def demo_streaming():
    """Demo streaming workflow execution."""

    from src.core.memory import MemoryManager

    memory_manager = MemoryManager(...)  # Initialize

    async for state in execute_research_workflow_streaming(
        topic="AI governance 2025",
        user_id="user-123",
        memory_manager=memory_manager
    ):
        print(f"Status: {state.status}, Quality: {state.quality_score:.2f}")

        if state.status == "finished":
            print(f"Final answer: {state.refined_answer[:200]}...")
            break
```

### OpenTelemetry Integration

```python
"""OpenTelemetry tracing for LangGraph execution."""

from src.core.telemetry import get_tracer, trace_agent_operation


@trace_agent_operation("research_workflow")
async def execute_research_workflow(
    topic: str,
    user_id: str,
    memory_manager: MemoryManager
) -> ResearchState:
    """Execute research workflow with full OpenTelemetry tracing.

    Creates parent span "agent.research_workflow" with child spans
    for each node execution.

    Args:
        topic: Research topic
        user_id: User identifier
        memory_manager: MemoryManager dependency

    Returns:
        Final ResearchState after completion
    """

    tracer = get_tracer("workflow")

    with tracer.start_as_current_span("langgraph.research_workflow") as span:
        # Set span attributes
        span.set_attribute("topic", topic)
        span.set_attribute("user_id", user_id)
        span.set_attribute("max_iterations", 5)

        # Create and compile graph
        graph = create_research_graph()

        # Initialize state
        initial_state = ResearchState(
            topic=topic,
            user_id=user_id,
            iteration_count=0,
            status="planning"
        )

        # Execute graph (nodes create child spans automatically)
        final_state = await graph.ainvoke(initial_state)

        # Record results
        span.set_attribute("iterations_used", final_state.iteration_count)
        span.set_attribute("quality_score", final_state.quality_score)
        span.set_attribute("sources_count", len(final_state.sources))
        span.set_attribute("status", final_state.status)

        return final_state
```

### Trace Hierarchy

```
agent.research_workflow
└── langgraph.research_workflow
    ├── langgraph.node.plan
    │   └── agent.run (from trace_agent_operation)
    ├── langgraph.node.research (iteration=0)
    │   └── agent.run
    │       └── mcp.tool_call.search (from trace_tool_call)
    ├── langgraph.node.critique (iteration=0)
    │   └── agent.run
    ├── langgraph.edge.should_continue_research → refine
    ├── langgraph.node.refine (iteration=1)
    │   └── agent.run
    ├── langgraph.node.research (iteration=1)
    │   └── agent.run
    │       └── mcp.tool_call.search
    └── ... (continues for up to 5 iterations)
```

---

## 7. Complete Working Example

### Full Implementation

```python
"""Complete research workflow implementation with LangGraph."""

from typing import Literal, Optional
from datetime import datetime
import logging

from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from src.core.llm import get_azure_model, parse_agent_result
from src.core.telemetry import trace_agent_operation, get_tracer
from src.core.memory import MemoryManager
from src.agents.researcher import setup_researcher_agent, run_agent_with_tracing
from src.models.agent_response import AgentResponse


logger = logging.getLogger(__name__)


# ==================== State Model ====================

class SourceReference(BaseModel):
    title: str
    url: str
    snippet: str
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)


class ResearchState(BaseModel):
    # Input
    topic: str
    user_id: str

    # Workflow state
    plan: Optional[str] = None
    sources: list[SourceReference] = Field(default_factory=list)
    critique: Optional[str] = None
    refined_answer: Optional[str] = None

    # Control
    iteration_count: int = 0
    status: Literal["planning", "researching", "critiquing", "refining", "finished"] = "planning"
    quality_score: float = 0.0

    # Config
    max_iterations: int = 5
    quality_threshold: float = 0.8

    class Config:
        arbitrary_types_allowed = True


# ==================== Nodes ====================

async def plan_node(state: ResearchState) -> ResearchState:
    """Generate research plan."""
    logger.info("📋 [PLAN] Generating plan for: %s", state.topic)

    model = get_azure_model()
    planner = Agent[None, str](
        model=model,
        output_type=str,
        system_prompt="Create a focused 3-step research plan."
    )

    result = await planner.run(f"Plan: {state.topic}")
    state.plan = parse_agent_result(result)
    state.status = "researching"

    return state


async def research_node(state: ResearchState, memory_manager: MemoryManager) -> ResearchState:
    """Execute research."""
    logger.info("🔬 [RESEARCH] Iteration %d/%d", state.iteration_count + 1, state.max_iterations)

    agent, mcp_session = await setup_researcher_agent(memory_manager)

    try:
        response: AgentResponse = await run_agent_with_tracing(
            agent=agent,
            task=f"Research: {state.topic}\nPlan: {state.plan}",
            deps=memory_manager,
            mcp_session=mcp_session
        )

        # Extract sources from tool calls
        new_sources = []
        for tc in response.tool_calls:
            if tc.tool_name == "search" and tc.status.value == "success":
                if isinstance(tc.result, list):
                    for item in tc.result[:5]:
                        if isinstance(item, dict):
                            new_sources.append(SourceReference(
                                title=item.get("title", ""),
                                url=item.get("url", ""),
                                snippet=item.get("snippet", "")[:500],
                                retrieved_at=datetime.utcnow()
                            ))

        state.sources.extend(new_sources)
        state.iteration_count += 1
        state.status = "critiquing"

        return state

    finally:
        if hasattr(mcp_session, "_close_cm"):
            await mcp_session._close_cm.__aexit__(None, None, None)


class CritiqueResult(BaseModel):
    quality_score: float = Field(ge=0.0, le=1.0)
    critique: str


async def critique_node(state: ResearchState) -> ResearchState:
    """Assess quality."""
    logger.info("🔍 [CRITIQUE] Evaluating iteration %d", state.iteration_count)

    model = get_azure_model()
    critic = Agent[None, CritiqueResult](
        model=model,
        output_type=CritiqueResult,
        system_prompt="Evaluate research quality (0.0-1.0)."
    )

    result = await critic.run(f"Critique: {state.topic}\nSources: {len(state.sources)}")
    critique_result: CritiqueResult = parse_agent_result(result)

    state.quality_score = critique_result.quality_score
    state.critique = critique_result.critique

    return state


async def refine_node(state: ResearchState) -> ResearchState:
    """Refine answer."""
    logger.info("✨ [REFINE] Improving answer")

    model = get_azure_model()
    refiner = Agent[None, str](
        model=model,
        output_type=str,
        system_prompt="Synthesize research into comprehensive answer."
    )

    result = await refiner.run(f"Refine: {state.critique}")
    state.refined_answer = parse_agent_result(result)
    state.status = "researching"

    return state


async def finish_node(state: ResearchState, memory_manager: MemoryManager) -> ResearchState:
    """Finalize."""
    logger.info("🎯 [FINISH] Finalizing")

    report_md = f"""# {state.topic}

Quality: {state.quality_score:.2f}
Iterations: {state.iteration_count}

{state.refined_answer}

## Sources
{chr(10).join([f"- [{s.title}]({s.url})" for s in state.sources])}
"""

    await memory_manager.store_document(
        content=report_md,
        metadata={"topic": state.topic, "user_id": state.user_id}
    )

    state.status = "finished"
    return state


# ==================== Routing ====================

def should_continue_research(state: ResearchState) -> Literal["refine", "finish"]:
    """Decide: continue or finish."""

    if state.iteration_count >= state.max_iterations:
        logger.warning("⚠️ Max iterations reached")
        return "finish"

    if state.quality_score >= state.quality_threshold:
        logger.info("✅ Quality threshold met")
        return "finish"

    return "refine"


# ==================== Graph ====================

def create_research_graph(memory_manager: MemoryManager) -> StateGraph:
    """Build graph."""

    graph = StateGraph(ResearchState)

    # Nodes
    graph.add_node("plan", plan_node)
    graph.add_node("research", lambda s: research_node(s, memory_manager))
    graph.add_node("critique", critique_node)
    graph.add_node("refine", refine_node)
    graph.add_node("finish", lambda s: finish_node(s, memory_manager))

    # Edges
    graph.set_entry_point("plan")
    graph.add_edge("plan", "research")
    graph.add_edge("research", "critique")
    graph.add_conditional_edges(
        "critique",
        should_continue_research,
        {"refine": "refine", "finish": "finish"}
    )
    graph.add_edge("refine", "research")
    graph.add_edge("finish", END)

    return graph.compile()


# ==================== Execution ====================

@trace_agent_operation("research_workflow")
async def execute_research_workflow(
    topic: str,
    user_id: str,
    memory_manager: MemoryManager
) -> ResearchState:
    """Execute workflow."""

    logger.info("🚀 Starting workflow: %s", topic)

    graph = create_research_graph(memory_manager)
    initial_state = ResearchState(topic=topic, user_id=user_id)
    final_state = await graph.ainvoke(initial_state)

    logger.info("🎉 Complete | Iterations: %d | Quality: %.2f",
                final_state.iteration_count, final_state.quality_score)

    return final_state
```

---

## 8. Testing Patterns

### Unit Tests

```python
"""Unit tests for LangGraph nodes."""

import pytest
from src.workflows.research_graph import should_continue_research
from src.models.research_state import ResearchState


def test_should_continue_max_iterations():
    """Test hard stop at max iterations."""

    state = ResearchState(
        topic="test",
        user_id="test-user",
        iteration_count=5,
        max_iterations=5,
        quality_score=0.5
    )

    assert should_continue_research(state) == "finish"


def test_should_continue_quality_met():
    """Test finish when quality threshold met."""

    state = ResearchState(
        topic="test",
        user_id="test-user",
        iteration_count=2,
        max_iterations=5,
        quality_score=0.85,
        quality_threshold=0.8
    )

    assert should_continue_research(state) == "finish"


def test_should_continue_needs_refinement():
    """Test continue when quality low."""

    state = ResearchState(
        topic="test",
        user_id="test-user",
        iteration_count=2,
        max_iterations=5,
        quality_score=0.6,
        quality_threshold=0.8
    )

    assert should_continue_research(state) == "refine"
```

### Integration Tests

```python
"""Integration test for complete workflow."""

import pytest
from src.workflows.research_graph import execute_research_workflow
from src.core.memory import MemoryManager


@pytest.mark.asyncio
async def test_workflow_end_to_end(memory_manager: MemoryManager):
    """Test complete workflow execution."""

    final_state = await execute_research_workflow(
        topic="Python 3.12 features",
        user_id="test-user",
        memory_manager=memory_manager
    )

    # Verify completion
    assert final_state.status == "finished"
    assert final_state.iteration_count <= final_state.max_iterations
    assert len(final_state.sources) > 0
    assert 0.0 <= final_state.quality_score <= 1.0
    assert final_state.refined_answer is not None
```

---

## 9. Summary

### Key Patterns

1. **Pydantic State**: Type-safe state with validation
2. **Cyclical Graph**: Plan → Research → Critique → Refine (loop) → Finish
3. **Hard Limits**: Enforced at conditional edge
4. **MCP Integration**: Reuse existing ResearcherAgent
5. **Streaming**: `graph.astream()` for real-time updates
6. **Observability**: OpenTelemetry spans at all levels

### Dependencies

```toml
[project]
dependencies = [
    # ... existing
    "langgraph>=0.2.0",  # State machine orchestration
]
```

### File Structure

```
src/workflows/
├── __init__.py
├── research_graph.py      # Graph + nodes + routing
├── research_state.py      # ResearchState model (or in src/models/)
└── report_formatter.py    # Markdown generation
```

---

**End of Research Document**
