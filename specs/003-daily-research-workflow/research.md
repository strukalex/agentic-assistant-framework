# Research Findings: DailyTrendingResearch Workflow

**Feature Branch**: `003-daily-research-workflow`
**Research Date**: 2025-12-24
**Status**: Complete

This document consolidates research findings for implementing the DailyTrendingResearch Workflow with Windmill orchestration and LangGraph cyclical reasoning. For detailed research information, take a lookat at `research_detailed.md`

---

## 1. LangGraph State Machine Implementation

### Decision: Use LangGraph StateGraph with Pydantic BaseModel for State

**Rationale**:
- LangGraph's `StateGraph` class provides explicit state machine modeling with cycles support
- Pydantic `BaseModel` offers type safety consistent with existing codebase patterns
- Conditional edges enable dynamic routing (Critique→Refine vs Critique→Finish)
- Built-in support for iteration limits via state field checks

**Alternatives Considered**:
- **TypedDict**: Simpler but lacks Pydantic validation; rejected for consistency with existing models
- **Custom state machine**: More control but reinvents wheel; rejected for maintenance burden

### Implementation Pattern

from typing import List, Optional
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END

class ResearchState(BaseModel):
topic: str
plan: Optional[str] = None
sources: List[dict] = []
critique: Optional[str] = None
refined_answer: Optional[str] = None
iteration_count: int = 0
status: str = "planning"

def should_continue(state: ResearchState) -> str:
"""Route based on iteration count and quality."""
if state.iteration_count >= 5: # Hard limit per FR-005
return "finish"
if state.status == "needs_refinement":
return "refine"
return "finish"

Build graph
graph = StateGraph(ResearchState)
graph.add_node("plan", plan_node)
graph.add_node("research", research_node)
graph.add_node("critique", critique_node)
graph.add_node("refine", refine_node)
graph.add_node("finish", finish_node)

graph.add_edge(START, "plan")
graph.add_edge("plan", "research")
graph.add_edge("research", "critique")
graph.add_conditional_edges("critique", should_continue, {
"refine": "refine",
"finish": "finish"
})
graph.add_edge("refine", "research") # Cycle back
graph.add_edge("finish", END)

compiled = graph.compile()

text

### Key Sources
- [LangGraph Overview - LangChain Docs](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph StateGraph Conditional Edges - DEV Community](https://dev.to/jamesli/advanced-langgraph-implementing-conditional-edges-and-tool-calling-agents-3pdn)
- [LangGraph Tutorial - DataCamp](https://www.datacamp.com/tutorial/langgraph-tutorial)

---

## 2. Windmill + LangGraph Integration

### Decision: Embed LangGraph as Python Library within Windmill Step

**Rationale**:
- Windmill executes Python scripts as workflow steps with full library access
- LangGraph compiles to an executable graph that runs within a single Python process
- State can be serialized/deserialized between Windmill steps if needed
- Avoids microservice overhead; single-process execution for the research loop

**Alternatives Considered**:
- **Separate LangGraph microservice**: More isolation but adds network latency and deployment complexity; rejected per constitution preference for embedded execution
- **Pure Windmill DAG**: No support for cycles; would require manual loop implementation; rejected as LangGraph provides cleaner abstraction

### Integration Pattern

windmill/daily_research.py - Windmill workflow step
import wmill
from src.workflows.research_graph import build_research_graph
from src.models.research_state import ResearchState

def main(topic: str, user_id: str):
"""Windmill step that runs the LangGraph research loop."""
# Build and compile the graph
graph = build_research_graph()

text
# Initialize state
initial_state = ResearchState(topic=topic)

# Execute the graph (runs all cycles in-process)
final_state = graph.invoke(initial_state)

# Return result for next Windmill step
return {
    "report": final_state.refined_answer,
    "sources": final_state.sources,
    "iterations": final_state.iteration_count
}
text

### Key Sources
- [Windmill Getting Started](https://www.windmill.dev/docs/getting_started/how_to_use_windmill)
- [LangGraph Production Usage - LangChain Blog](https://blog.langchain.com/langgraph/)

---

## 3. Windmill Approval Gates

### Decision: Use Windmill Native Suspend/Resume with 5-Minute Timeout

**Rationale**:
- Windmill's built-in approval system generates unique URLs for resume/cancel
- Native timeout configuration handles 5-minute requirement (FR-007)
- Approval state persists across workflow suspension
- Integrates with Windmill's flow architecture without custom implementation

**Alternatives Considered**:
- **Custom polling loop**: More control but blocks worker; rejected for resource efficiency
- **External approval service**: Adds dependency; rejected for simplicity

### Implementation Pattern

windmill/approval_handler.py
import wmill

def request_approval(action_type: str, action_description: str):
"""Request human approval for REVERSIBLE_WITH_DELAY actions."""
urls = wmill.get_resume_urls()

text
return {
    "resume": urls["resume"],
    "cancel": urls["cancel"],
    "action_type": action_type,
    "description": action_description,
    "default_args": {"decision": "pending"},
    "enums": {"decision": ["approve", "reject"]}
}
In flow configuration (via Windmill UI or OpenFlow):
- Enable "Suspend" in step advanced settings
- Set timeout to 300 seconds (5 minutes)
- Configure "Continue on timeout" to handle escalation
text

### Timeout Escalation Pattern

def handle_approval_result(resume_payload: dict):
"""Process approval result, handling timeout/rejection."""
if "error" in resume_payload:
# Timeout or rejection occurred
log_escalation(resume_payload["error"])
return {"action_taken": False, "reason": "escalated"}

text
# Approval received
return {"action_taken": True, "approver": resume_payload.get("approver")}
text

### Key Sources
- [Windmill Suspend & Approval Docs](https://www.windmill.dev/docs/flows/flow_approval)
- [Windmill Flow Architecture](https://www.windmill.dev/docs/flows/architecture)

---

## 4. OpenTelemetry Instrumentation for LangGraph

### Decision: Custom Span Creation per Node with Existing Telemetry Module

**Rationale**:
- Extend existing `src/core/telemetry.py` with LangGraph-specific decorators
- Create parent span for full graph execution, child spans per node
- Capture iteration count and state transitions as span attributes
- Consistent with existing `@trace_agent_operation` and `@trace_tool_call` patterns

**Alternatives Considered**:
- **LangSmith integration**: Vendor lock-in; rejected for OpenTelemetry standardization
- **Langfuse callback**: External dependency; rejected for self-hosted preference
- **Automatic instrumentation only**: Insufficient detail; rejected for observability requirements

### Implementation Pattern

src/core/telemetry.py - Extended
from opentelemetry import trace
from functools import wraps

def trace_langgraph_node(node_name: str):
"""Decorator for tracing LangGraph node execution."""
def decorator(func):
@wraps(func)
async def wrapper(state, *args, **kwargs):
tracer = get_tracer("langgraph")
with tracer.start_as_current_span(f"langgraph.node.{node_name}") as span:
span.set_attribute("component", "langgraph")
span.set_attribute("node.name", node_name)
span.set_attribute("iteration_count", state.iteration_count)
span.set_attribute("state.status", state.status)

text
            try:
                result = await func(state, *args, **kwargs)
                span.set_attribute("operation.success", True)
                return result
            except Exception as e:
                span.set_attribute("operation.success", False)
                span.set_attribute("error.message", str(e))
                raise
    return wrapper
return decorator
def trace_langgraph_execution(workflow_name: str):
"""Decorator for tracing full LangGraph execution."""
def decorator(func):
@wraps(func)
async def wrapper(*args, **kwargs):
tracer = get_tracer("langgraph")
with tracer.start_as_current_span(f"langgraph.workflow.{workflow_name}") as span:
span.set_attribute("component", "langgraph")
span.set_attribute("workflow.name", workflow_name)

text
            result = await func(*args, **kwargs)

            # Capture final metrics
            if hasattr(result, "iteration_count"):
                span.set_attribute("total_iterations", result.iteration_count)
            span.set_attribute("operation.success", True)
            return result
    return wrapper
return decorator
text

### Semantic Conventions (OpenTelemetry Gen AI)

Per emerging OpenTelemetry standards for AI agents:
- `gen_ai.agent.name`: Agent identifier
- `gen_ai.request.model`: Model used
- `gen_ai.usage.input_tokens`: Input token count
- `gen_ai.usage.output_tokens`: Output token count

### Key Sources
- [LangSmith OpenTelemetry Integration](https://blog.langchain.com/end-to-end-opentelemetry-langsmith/)
- [OpenTelemetry Gen AI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai)
- [OpenTelemetry LangGraph Example](https://github.com/CVxTz/opentelemetry-langgraph-langchain-example)

---

## 5. Worker Isolation and Resource Limits

### Decision: Windmill Worker Memory Sizing + PID Namespace Isolation

**Rationale**:
- Windmill workers naturally isolate job execution per worker process
- Configure workers with 2GB memory per FR-010 requirement
- Enable PID namespace isolation for security (prevents environment variable leakage)
- Use native Windmill resource limits rather than custom subprocess management

**Alternatives Considered**:
- **NSJAIL sandboxing**: More comprehensive but complex setup; deferred to production hardening
- **Manual subprocess isolation**: Duplicates Windmill functionality; rejected

### Configuration Pattern

docker-compose.yml for Windmill workers
services:
windmill_worker:
image: ghcr.io/windmill-labs/windmill:latest
environment:
- DATABASE_URL=${DATABASE_URL}
- ENABLE_UNSHARE_PID=true # PID namespace isolation
deploy:
resources:
limits:
cpus: '1' # 1 CPU core per FR-010
memory: 2G # 2GB memory per FR-010

text

### Key Sources
- [Windmill Security and Isolation](https://www.windmill.dev/docs/advanced/security_isolation)
- [Windmill Workers and Worker Groups](https://www.windmill.dev/docs/core_concepts/worker_groups)
- [Windmill Scaling](https://www.windmill.dev/docs/advanced/scaling)

---

## 6. Dependencies to Add

### New Python Dependencies

pyproject.toml additions
dependencies = [
# ... existing ...
"langgraph>=0.2.0", # LangGraph state machine
"wmill>=1.380.0", # Windmill Python client
]

text

### Version Compatibility Notes

- **LangGraph 0.2.0+**: Stable API for StateGraph, conditional edges, and compilation
- **wmill 1.380.0+**: Includes `get_resume_urls()` and latest approval API
- **pydantic-ai**: Already present; works seamlessly with LangGraph Pydantic states

---

## 7. Integration with Existing Codebase

### ResearcherAgent Integration

The existing `ResearcherAgent` from Spec 002 will be invoked within the LangGraph "research" node:

src/workflows/nodes/research.py
from src.agents.researcher import run_researcher_agent
from src.core.telemetry import trace_langgraph_node

@trace_langgraph_node("research")
async def research_node(state: ResearchState) -> ResearchState:
"""Execute research using existing ResearcherAgent."""
# Build query from plan
query = f"Research the following topic: {state.topic}\n\nFocus on: {state.plan}"

text
# Use existing agent
result = await run_researcher_agent(query, deps=memory_manager)

# Update state
state.sources.extend(result.tool_calls)  # Capture sources from tool calls
state.refined_answer = result.answer
state.iteration_count += 1

return state
text

### MemoryManager Integration

Final reports stored via existing MemoryManager abstraction:

src/workflows/nodes/finish.py
from src.core.memory import MemoryManager
from src.core.telemetry import trace_langgraph_node

@trace_langgraph_node("finish")
async def finish_node(state: ResearchState, memory: MemoryManager) -> ResearchState:
"""Format and store final research report."""
# Generate markdown report
report = format_research_report(state)

text
# Store via existing memory abstraction
await memory.store_document(
    content=report,
    metadata={
        "topic": state.topic,
        "sources": state.sources,
        "iterations": state.iteration_count,
        "type": "research_report"
    }
)

state.status = "complete"
return state
text

---

## Summary

| Area | Decision | Rationale |
|------|----------|-----------|
| State Machine | LangGraph StateGraph + Pydantic | Type safety, cycle support, consistent with codebase |
| Integration | LangGraph embedded in Windmill step | Single-process, no network overhead |
| Approvals | Windmill native suspend/resume | Built-in timeout, URL-based approval |
| Telemetry | Extended telemetry.py with LangGraph decorators | Unified observability per Article II.H |
| Isolation | Windmill worker limits + PID namespace | Meets FR-010, minimal config |
| Iteration Limit | State field check in conditional edge | Hard limit of 5 per FR-005 |