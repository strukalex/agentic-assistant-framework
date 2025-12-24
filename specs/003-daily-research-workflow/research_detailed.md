# Research: OpenTelemetry Instrumentation for LangGraph Workflows

**Feature**: 003-daily-research-workflow
**Date**: 2025-12-24
**Purpose**: Resolve technical unknowns for instrumenting LangGraph with OpenTelemetry

## Research Questions

### RQ-001: How to Create Spans for Each LangGraph Node Entry/Exit

**Question**: What is the best approach to instrument LangGraph nodes with OpenTelemetry spans?

**Decision**: Use custom decorators that wrap node functions with manual span creation, leveraging the existing unified telemetry module (`src/core/telemetry.py`)

**Rationale**:
- LangGraph nodes are regular Python functions that can be wrapped with decorators
- Pattern for node instrumentation:
  ```python
  from opentelemetry import trace
  from src.core.telemetry import get_tracer

  def trace_langgraph_node(node_name: str):
      """
      Decorator to instrument LangGraph nodes with OpenTelemetry spans.

      Usage:
          @trace_langgraph_node("plan")
          async def plan_node(state: ResearchState) -> ResearchState:
              ...
      """
      def decorator(func):
          tracer = get_tracer("workflow")

          @wraps(func)
          async def wrapper(*args, **kwargs):
              with tracer.start_as_current_span(f"langgraph.node.{node_name}") as span:
                  # Set standard attributes
                  span.set_attribute("node.name", node_name)
                  span.set_attribute("node.type", "graph_node")
                  span.set_attribute("component", "workflow")

                  # Extract state information (first arg is typically state)
                  if args:
                      state = args[0]
                      if hasattr(state, "iteration_count"):
                          span.set_attribute("state.iteration_count", state.iteration_count)
                      if hasattr(state, "topic"):
                          span.set_attribute("state.topic", state.topic)

                  try:
                      result = await func(*args, **kwargs)
                      span.set_attribute("operation.success", True)

                      # Capture result state changes
                      if hasattr(result, "status"):
                          span.set_attribute("state.status", result.status)

                      return result
                  except Exception as exc:
                      span.set_attribute("operation.success", False)
                      span.record_exception(exc)
                      raise

          return wrapper
      return decorator
  ```

- Node implementation example:
  ```python
  @trace_langgraph_node("plan")
  async def plan_node(state: ResearchState) -> ResearchState:
      """Generate research plan based on topic."""
      # Node logic here
      return updated_state

  @trace_langgraph_node("research")
  async def research_node(state: ResearchState) -> ResearchState:
      """Execute research based on plan."""
      # Node logic here
      return updated_state
  ```

**Span Attributes for Nodes**:
- `node.name`: Node identifier (plan, research, critique, refine, finish)
- `node.type`: Always "graph_node"
- `component`: Always "workflow"
- `state.iteration_count`: Current iteration number (for loop detection)
- `state.topic`: Research topic (for context)
- `state.status`: Node output status
- `operation.success`: Boolean indicating success/failure

**Alternative Considered**:
- LangChain/LangGraph auto-instrumentation: Not available as of Jan 2025; manual instrumentation provides better control and aligns with Constitution Article II.H (unified telemetry)

**References**:
- Existing pattern from `src/core/telemetry.py`: `trace_agent_operation()` and `trace_tool_call()`
- OpenTelemetry Semantic Conventions: https://opentelemetry.io/docs/specs/semconv/

---

### RQ-002: How to Capture State Transitions and Conditional Edge Decisions

**Question**: How should OpenTelemetry spans capture LangGraph state transitions and edge routing logic?

**Decision**: Create spans for edge evaluation with attributes capturing the decision logic and destination node

**Rationale**:
- LangGraph edges determine which node to execute next based on state
- Pattern for edge instrumentation:
  ```python
  from opentelemetry import trace
  from src.core.telemetry import get_tracer

  def trace_edge_decision(edge_name: str):
      """
      Decorator to trace conditional edge routing decisions.

      Usage:
          @trace_edge_decision("should_continue")
          def should_continue_edge(state: ResearchState) -> str:
              ...
      """
      def decorator(func):
          tracer = get_tracer("workflow")

          @wraps(func)
          def wrapper(*args, **kwargs):
              with tracer.start_as_current_span(f"langgraph.edge.{edge_name}") as span:
                  # Set standard attributes
                  span.set_attribute("edge.name", edge_name)
                  span.set_attribute("edge.type", "conditional")
                  span.set_attribute("component", "workflow")

                  # Capture state before decision
                  if args:
                      state = args[0]
                      if hasattr(state, "iteration_count"):
                          span.set_attribute("state.iteration_count", state.iteration_count)
                      if hasattr(state, "status"):
                          span.set_attribute("state.status", state.status)

                  try:
                      # Execute edge logic
                      next_node = func(*args, **kwargs)

                      # Capture routing decision
                      span.set_attribute("edge.next_node", next_node)
                      span.set_attribute("operation.success", True)

                      # Add event for state transition
                      span.add_event(
                          "state_transition",
                          attributes={
                              "from_status": getattr(args[0], "status", "unknown"),
                              "to_node": next_node
                          }
                      )

                      return next_node
                  except Exception as exc:
                      span.set_attribute("operation.success", False)
                      span.record_exception(exc)
                      raise

          return wrapper
      return decorator
  ```

- Edge function example (for DailyTrendingResearch workflow):
  ```python
  @trace_edge_decision("should_continue_research")
  def should_continue_research(state: ResearchState) -> str:
      """
      Determine if research should continue based on iteration count and quality.

      Returns:
          "refine" if iteration < 5 and quality insufficient
          "finish" if iteration >= 5 or quality sufficient
      """
      # Check max iterations (FR-005: limit to 5 iterations)
      if state.iteration_count >= 5:
          return "finish"

      # Check if critique indicates sufficient quality
      if state.critique and "sufficient" in state.critique.lower():
          return "finish"

      # Otherwise continue refining
      return "refine"
  ```

**Span Attributes for Edges**:
- `edge.name`: Edge identifier (should_continue_research, etc.)
- `edge.type`: "conditional" or "static"
- `edge.next_node`: Destination node name
- `state.iteration_count`: Current iteration (critical for loop analysis)
- `state.status`: Current state status
- `operation.success`: Boolean indicating successful routing

**State Transition Events**:
Use `span.add_event()` to capture discrete state transitions:
```python
span.add_event(
    "state_transition",
    attributes={
        "from_status": state.status,
        "to_node": next_node,
        "iteration": state.iteration_count,
        "decision_reason": "max_iterations_reached"
    }
)
```

**References**:
- OpenTelemetry Span Events: https://opentelemetry.io/docs/concepts/signals/traces/#span-events
- LangGraph conditional edges: Pattern from spec.md FR-003, FR-004, FR-005

---

### RQ-003: Best Practices for Tracing Cyclical Graphs (Loops with Iteration Count)

**Question**: How to handle traces for cyclical LangGraph execution without creating infinite spans or losing iteration context?

**Decision**: Use iteration count as a span attribute and implement loop-aware span naming to differentiate iterations

**Rationale**:
- Cyclical graphs create multiple executions of the same node
- Each iteration should create a distinct span with clear iteration context
- Pattern for loop-aware tracing:
  ```python
  @trace_langgraph_node("critique")
  async def critique_node(state: ResearchState) -> ResearchState:
      """Critique current research findings."""
      # Iteration count is automatically captured by decorator
      # Each call creates a new span with state.iteration_count attribute

      state.iteration_count += 1  # Increment iteration

      # Critique logic here
      critique_result = await agent.run(f"Critique: {state.refined_answer}")

      state.critique = critique_result.data.critique
      return state
  ```

- Span structure for iterative execution:
  ```
  langgraph.execution
  ├── langgraph.node.plan (iteration=0)
  ├── langgraph.node.research (iteration=0)
  ├── langgraph.node.critique (iteration=0)
  ├── langgraph.edge.should_continue_research → refine
  ├── langgraph.node.refine (iteration=1)
  ├── langgraph.node.research (iteration=1)
  ├── langgraph.node.critique (iteration=1)
  ├── langgraph.edge.should_continue_research → refine
  ├── langgraph.node.refine (iteration=2)
  └── ... (up to iteration=5 per FR-005)
  ```

**Key Attributes for Loop Tracking**:
1. `state.iteration_count`: Monotonically increasing counter (0-based)
2. `loop.max_iterations`: Maximum allowed iterations (e.g., 5 per FR-005)
3. `loop.exit_reason`: Why the loop terminated
   - "max_iterations_reached"
   - "quality_threshold_met"
   - "error_occurred"

**Loop Exit Span**:
Create a synthetic span when loop exits to capture final state:
```python
def trace_loop_exit(state: ResearchState, reason: str):
    """Create a span documenting loop exit."""
    tracer = get_tracer("workflow")
    with tracer.start_as_current_span("langgraph.loop_exit") as span:
        span.set_attribute("loop.exit_reason", reason)
        span.set_attribute("loop.total_iterations", state.iteration_count)
        span.set_attribute("loop.max_iterations", 5)  # From FR-005
        span.set_attribute("component", "workflow")

        if hasattr(state, "refined_answer"):
            span.set_attribute("loop.has_result", True)

        span.add_event(
            "research_loop_completed",
            attributes={
                "iterations": state.iteration_count,
                "exit_reason": reason
            }
        )
```

**Performance Considerations**:
- Each iteration creates 3-4 spans (node + edge + possible sub-spans)
- For 5 iterations: ~15-20 spans per workflow execution
- Ensure OTLP exporter uses batching (already configured in `src/core/telemetry.py`)

**Alternatives Considered**:
- Single span for entire loop: Rejected because loses per-iteration visibility
- Span links between iterations: Rejected because adds complexity without significant benefit

**References**:
- OpenTelemetry Span Attributes: https://opentelemetry.io/docs/specs/semconv/general/attributes/
- Spec FR-005: Maximum 5 iterations enforcement

---

### RQ-004: How to Correlate LangGraph Traces with Parent Windmill Workflow Traces

**Question**: How to maintain trace context between Windmill workflow steps and embedded LangGraph execution?

**Decision**: Use OpenTelemetry context propagation with explicit parent span IDs passed from Windmill to LangGraph

**Rationale**:
- Windmill workflow executes as parent orchestrator
- LangGraph runs as embedded library within Windmill step
- Pattern for context propagation:
  ```python
  from opentelemetry import trace, context
  from opentelemetry.trace import set_span_in_context

  # In Windmill workflow step
  def windmill_research_step(topic: str, user_id: str, trace_parent: str = None):
      """
      Windmill workflow step that executes LangGraph research.

      Args:
          topic: Research topic
          user_id: User identifier
          trace_parent: W3C Trace Context traceparent header (optional)
      """
      tracer = get_tracer("workflow")

      # Create span for Windmill step
      with tracer.start_as_current_span("windmill.research_step") as windmill_span:
          windmill_span.set_attribute("windmill.step_name", "research")
          windmill_span.set_attribute("workflow.topic", topic)
          windmill_span.set_attribute("workflow.user_id", user_id)
          windmill_span.set_attribute("component", "windmill")

          # Execute LangGraph with inherited context
          # Context is automatically propagated to child spans
          result = await execute_research_graph(topic, user_id)

          # Capture result metadata
          windmill_span.set_attribute("result.iterations", result.iteration_count)
          windmill_span.set_attribute("result.has_sources", len(result.sources) > 0)

          return result
  ```

- LangGraph execution function:
  ```python
  async def execute_research_graph(topic: str, user_id: str) -> ResearchReport:
      """
      Execute LangGraph research loop.

      This function runs within Windmill step context - spans are automatically
      children of the active Windmill span.
      """
      tracer = get_tracer("workflow")

      # Create root span for LangGraph execution
      # This will be a child of windmill.research_step
      with tracer.start_as_current_span("langgraph.execution") as graph_span:
          graph_span.set_attribute("graph.name", "research")
          graph_span.set_attribute("graph.topic", topic)
          graph_span.set_attribute("component", "workflow")

          # Initialize state
          state = ResearchState(topic=topic, iteration_count=0)

          # Execute graph (nodes create their own child spans)
          graph = build_research_graph()
          final_state = await graph.ainvoke(state)

          # Capture final state
          graph_span.set_attribute("graph.final_iteration", final_state.iteration_count)
          graph_span.set_attribute("graph.status", final_state.status)

          return format_research_report(final_state)
  ```

**Trace Hierarchy**:
```
windmill.workflow (Windmill root - may not be instrumented)
└── windmill.research_step
    └── langgraph.execution
        ├── langgraph.node.plan
        │   └── agent.run (from trace_agent_operation)
        │       └── mcp.tool_call.web_search (from trace_tool_call)
        ├── langgraph.node.research
        │   └── agent.run
        │       └── mcp.tool_call.web_search
        ├── langgraph.node.critique
        ├── langgraph.edge.should_continue_research
        └── ... (iterations)
```

**W3C Trace Context Propagation** (if Windmill supports it):
```python
from opentelemetry.propagate import extract, inject

# In Windmill step (if Windmill provides trace headers)
carrier = {"traceparent": trace_parent_header}
ctx = extract(carrier)

# Execute LangGraph with extracted context
with trace.use_span(span, end_on_exit=True):
    result = await execute_research_graph(topic, user_id)
```

**Windmill Integration Considerations**:
- If Windmill has native OpenTelemetry support: Use W3C Trace Context headers
- If Windmill doesn't support tracing: Create synthetic parent span at workflow entry
- Ensure consistent `service.name` attribute across Windmill and LangGraph spans

**Span Attributes for Correlation**:
- `windmill.workflow_id`: Unique workflow execution ID (if available)
- `windmill.step_name`: Current step name
- `windmill.job_id`: Windmill job identifier
- `workflow.user_id`: User context (for filtering)

**References**:
- W3C Trace Context: https://www.w3.org/TR/trace-context/
- OpenTelemetry Context Propagation: https://opentelemetry.io/docs/concepts/context-propagation/
- Windmill workflow structure: Per spec.md and plan.md

---

### RQ-005: Attribute Conventions for LLM/Agent Traces in OpenTelemetry

**Question**: What are the standard OpenTelemetry semantic conventions for LLM and agent operations?

**Decision**: Use OpenTelemetry GenAI Semantic Conventions (experimental as of Jan 2025) with custom attributes for agent-specific operations

**Rationale**:
- OpenTelemetry has draft semantic conventions for GenAI operations
- Standard attributes provide consistency across observability tools
- Pattern for LLM/Agent instrumentation:
  ```python
  from src.core.telemetry import trace_agent_operation

  @trace_agent_operation("run")
  async def run_agent(task: str, context: dict) -> AgentResponse:
      """Execute agent with full LLM tracing."""
      tracer = get_tracer("agent")

      with tracer.start_as_current_span("agent.run") as span:
          # GenAI Semantic Conventions
          span.set_attribute("gen_ai.system", "pydantic_ai")
          span.set_attribute("gen_ai.request.model", "deepseek-v3")
          span.set_attribute("gen_ai.request.max_tokens", 4096)
          span.set_attribute("gen_ai.request.temperature", 0.7)

          # Agent-specific attributes
          span.set_attribute("agent.type", "researcher")
          span.set_attribute("agent.task", task)
          span.set_attribute("agent.has_context", bool(context))

          # Execute agent
          result = await agent.run(task, deps=memory_manager)

          # Response attributes
          span.set_attribute("gen_ai.response.finish_reason", "complete")
          span.set_attribute("gen_ai.usage.prompt_tokens", result.usage.prompt_tokens)
          span.set_attribute("gen_ai.usage.completion_tokens", result.usage.completion_tokens)
          span.set_attribute("gen_ai.usage.total_tokens", result.usage.total_tokens)

          # Agent result attributes
          span.set_attribute("agent.confidence", result.data.confidence)
          span.set_attribute("agent.tool_calls_count", len(result.data.tool_calls))
          span.set_attribute("agent.has_sources", len(result.data.sources) > 0)

          return result
  ```

**Standard GenAI Attributes** (from OpenTelemetry Semantic Conventions):
- `gen_ai.system`: The LLM framework (e.g., "pydantic_ai", "langchain")
- `gen_ai.request.model`: Model name (e.g., "deepseek-v3", "gpt-4")
- `gen_ai.request.max_tokens`: Maximum tokens for response
- `gen_ai.request.temperature`: Sampling temperature
- `gen_ai.request.top_p`: Nucleus sampling parameter
- `gen_ai.response.id`: Unique response identifier
- `gen_ai.response.finish_reason`: "complete", "length", "content_filter"
- `gen_ai.usage.prompt_tokens`: Tokens in prompt
- `gen_ai.usage.completion_tokens`: Tokens in completion
- `gen_ai.usage.total_tokens`: Total tokens consumed

**Custom Agent Attributes** (project-specific):
- `agent.type`: Agent category (researcher, planner, critic, etc.)
- `agent.task`: Task description
- `agent.confidence`: Confidence score (0.0-1.0)
- `agent.tool_calls_count`: Number of tool invocations
- `agent.has_sources`: Boolean for citation presence
- `agent.memory_access_count`: Number of memory operations
- `agent.iteration`: Iteration number (for multi-turn agents)

**Tool Call Attributes** (already in `src/core/telemetry.py`):
```python
# From trace_tool_call decorator
span.set_attribute("tool_name", func.__name__)
span.set_attribute("parameters", str(kwargs))
span.set_attribute("result_count", len(result))
span.set_attribute("execution_duration_ms", duration_ms)
span.set_attribute("component", "mcp")
```

**Enhanced Tool Tracing for LangGraph Integration**:
```python
def trace_tool_call_enhanced(func):
    """Enhanced MCP tool tracing with parent context."""
    import time
    tracer = get_tracer("mcp")

    @wraps(func)
    async def wrapper(*args, **kwargs):
        with tracer.start_as_current_span(f"mcp.tool_call.{func.__name__}") as span:
            # Standard attributes (existing)
            span.set_attribute("tool_name", func.__name__)
            span.set_attribute("component", "mcp")
            span.set_attribute("operation.type", "tool_call")
            span.set_attribute("parameters", str(kwargs))

            # Enhanced attributes for LangGraph context
            # These capture which node triggered the tool call
            current_span = trace.get_current_span()
            if current_span:
                span_context = current_span.get_span_context()
                span.set_attribute("parent.trace_id", format(span_context.trace_id, '032x'))

            start_time = time.perf_counter()

            try:
                result = await func(*args, **kwargs)
                duration_ms = int((time.perf_counter() - start_time) * 1000)

                # Result attributes
                span.set_attribute("execution_duration_ms", duration_ms)
                span.set_attribute("result_count", len(result) if isinstance(result, list) else 1)
                span.set_attribute("operation.success", True)

                # Tool-specific result metadata
                if func.__name__ == "web_search" and isinstance(result, list):
                    span.set_attribute("search.result_count", len(result))
                    span.set_attribute("search.has_results", len(result) > 0)

                return result

            except Exception as exc:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                span.set_attribute("execution_duration_ms", duration_ms)
                span.set_attribute("operation.success", False)
                span.set_attribute("error_type", type(exc).__name__)
                span.set_attribute("error_message", str(exc))
                span.record_exception(exc)
                raise

    return wrapper
```

**Memory Operation Attributes** (already in `src/core/telemetry.py`):
```python
# From trace_memory_operation decorator
span.set_attribute("operation.type", operation_name)
span.set_attribute("db.system", "postgresql")
span.set_attribute("component", "memory")
span.set_attribute("operation.success", True/False)
```

**Unified Telemetry Architecture**:
All decorators follow Constitution Article II.H (Unified Telemetry):
- Single `src/core/telemetry.py` module
- Consistent attribute naming
- Service name: `paias` (not component-specific)
- Component filtering via `component` attribute

**References**:
- OpenTelemetry GenAI Semantic Conventions: https://opentelemetry.io/docs/specs/semconv/gen-ai/
- Existing implementation: `src/core/telemetry.py` lines 89-222
- Constitution Article II.H: docs/telemetry-refactoring.md

---

### RQ-006: Complete Instrumentation Pattern for LangGraph in Windmill

**Question**: What is the end-to-end instrumentation pattern for the DailyTrendingResearch workflow?

**Decision**: Implement a layered instrumentation approach with decorators at each level

**Implementation Pattern**:

```python
# File: src/workflows/research_graph.py

from functools import wraps
from opentelemetry import trace
from src.core.telemetry import get_tracer, trace_agent_operation, trace_tool_call
from langgraph.graph import StateGraph, END

# ============================================================================
# DECORATORS FOR LANGGRAPH-SPECIFIC INSTRUMENTATION
# ============================================================================

def trace_langgraph_node(node_name: str):
    """Decorator for LangGraph node functions."""
    def decorator(func):
        tracer = get_tracer("workflow")

        @wraps(func)
        async def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(f"langgraph.node.{node_name}") as span:
                span.set_attribute("node.name", node_name)
                span.set_attribute("node.type", "graph_node")
                span.set_attribute("component", "workflow")

                # Capture state context
                if args and hasattr(args[0], "iteration_count"):
                    state = args[0]
                    span.set_attribute("state.iteration_count", state.iteration_count)
                    span.set_attribute("state.topic", getattr(state, "topic", "unknown"))

                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("operation.success", True)
                    return result
                except Exception as exc:
                    span.set_attribute("operation.success", False)
                    span.record_exception(exc)
                    raise

        return wrapper
    return decorator


def trace_edge_decision(edge_name: str):
    """Decorator for LangGraph edge routing functions."""
    def decorator(func):
        tracer = get_tracer("workflow")

        @wraps(func)
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(f"langgraph.edge.{edge_name}") as span:
                span.set_attribute("edge.name", edge_name)
                span.set_attribute("edge.type", "conditional")
                span.set_attribute("component", "workflow")

                # Capture decision context
                if args and hasattr(args[0], "iteration_count"):
                    state = args[0]
                    span.set_attribute("state.iteration_count", state.iteration_count)

                try:
                    next_node = func(*args, **kwargs)
                    span.set_attribute("edge.next_node", next_node)
                    span.set_attribute("operation.success", True)

                    # Log state transition
                    span.add_event(
                        "routing_decision",
                        attributes={
                            "to_node": next_node,
                            "iteration": getattr(args[0], "iteration_count", 0)
                        }
                    )

                    return next_node
                except Exception as exc:
                    span.set_attribute("operation.success", False)
                    span.record_exception(exc)
                    raise

        return wrapper
    return decorator


# ============================================================================
# LANGGRAPH NODES (from plan.md structure)
# ============================================================================

@trace_langgraph_node("plan")
async def plan_node(state: ResearchState) -> ResearchState:
    """
    Generate research plan based on topic.

    Per FR-003: Plan node in cyclical research graph.
    """
    # Agent calls are automatically traced by trace_agent_operation decorator
    from src.agents.researcher import researcher_agent

    result = await researcher_agent.run(
        f"Create a research plan for: {state.topic}",
        deps=memory_manager
    )

    state.plan = result.data.plan
    return state


@trace_langgraph_node("research")
async def research_node(state: ResearchState) -> ResearchState:
    """
    Execute research based on plan.

    Per FR-003: Research node - uses ResearcherAgent with MCP tools.
    Per FR-012: Integrates ResearcherAgent from Spec 002.
    """
    from src.agents.researcher import researcher_agent

    # This will create child spans for agent.run and mcp.tool_call.*
    result = await researcher_agent.run(
        f"Research based on plan: {state.plan}",
        deps=memory_manager
    )

    state.sources.extend(result.data.sources)
    state.refined_answer = result.data.answer
    return state


@trace_langgraph_node("critique")
async def critique_node(state: ResearchState) -> ResearchState:
    """
    Critique current research findings.

    Per FR-003: Critique node identifies gaps.
    Per FR-005: Increments iteration_count.
    """
    from src.agents.researcher import researcher_agent

    result = await researcher_agent.run(
        f"Critique this research: {state.refined_answer}",
        deps=memory_manager
    )

    state.critique = result.data.critique
    state.iteration_count += 1  # Increment for loop tracking
    return state


@trace_langgraph_node("refine")
async def refine_node(state: ResearchState) -> ResearchState:
    """
    Refine answer based on critique.

    Per FR-003: Refine node improves answer based on critique feedback.
    """
    from src.agents.researcher import researcher_agent

    result = await researcher_agent.run(
        f"Refine research based on critique:\nCritique: {state.critique}\nCurrent: {state.refined_answer}",
        deps=memory_manager
    )

    state.refined_answer = result.data.refined_answer
    return state


@trace_langgraph_node("finish")
async def finish_node(state: ResearchState) -> ResearchState:
    """
    Finalize research and generate report.

    Per FR-003: Finish node generates final output.
    Per FR-008: Formats as Markdown report.
    """
    from src.workflows.report_formatter import format_research_report

    report = format_research_report(state)
    state.status = "completed"
    state.final_report = report

    return state


# ============================================================================
# LANGGRAPH EDGES
# ============================================================================

@trace_edge_decision("should_continue_research")
def should_continue_research(state: ResearchState) -> str:
    """
    Determine if research should continue.

    Per FR-005: Limit to 5 iterations maximum.

    Returns:
        "refine" if should continue
        "finish" if should terminate
    """
    # Max iterations check
    if state.iteration_count >= 5:
        return "finish"

    # Quality check
    if state.critique and "sufficient" in state.critique.lower():
        return "finish"

    return "refine"


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def build_research_graph() -> StateGraph:
    """
    Build the LangGraph state machine for research workflow.

    Per FR-003: Cyclical graph with Plan→Research→Critique→Refine→Finish.
    Per FR-004: Tracks state across iterations.
    """
    graph = StateGraph(ResearchState)

    # Add nodes
    graph.add_node("plan", plan_node)
    graph.add_node("research", research_node)
    graph.add_node("critique", critique_node)
    graph.add_node("refine", refine_node)
    graph.add_node("finish", finish_node)

    # Add edges
    graph.set_entry_point("plan")
    graph.add_edge("plan", "research")
    graph.add_edge("research", "critique")
    graph.add_conditional_edges(
        "critique",
        should_continue_research,
        {
            "refine": "refine",
            "finish": "finish"
        }
    )
    graph.add_edge("refine", "research")  # Loop back
    graph.add_edge("finish", END)

    return graph.compile()


# ============================================================================
# EXECUTION WITH WINDMILL INTEGRATION
# ============================================================================

async def execute_research_workflow(topic: str, user_id: str) -> ResearchReport:
    """
    Execute LangGraph research workflow with full instrumentation.

    This function is called from Windmill workflow step.
    Per FR-011: Emits OpenTelemetry spans at all levels.
    Per RQ-004: Inherits trace context from Windmill parent span.

    Args:
        topic: Research topic (FR-001: validated by caller)
        user_id: User identifier (FR-001: validated by caller)

    Returns:
        ResearchReport with findings and metadata
    """
    tracer = get_tracer("workflow")

    with tracer.start_as_current_span("langgraph.execution") as graph_span:
        # Set execution context attributes
        graph_span.set_attribute("graph.name", "research")
        graph_span.set_attribute("graph.topic", topic)
        graph_span.set_attribute("graph.user_id", user_id)
        graph_span.set_attribute("component", "workflow")

        try:
            # Initialize state
            state = ResearchState(
                topic=topic,
                iteration_count=0,
                sources=[],
                status="running"
            )

            # Build and execute graph
            graph = build_research_graph()
            final_state = await graph.ainvoke(state)

            # Capture final metrics
            graph_span.set_attribute("graph.final_iteration", final_state.iteration_count)
            graph_span.set_attribute("graph.status", final_state.status)
            graph_span.set_attribute("graph.source_count", len(final_state.sources))

            # Log completion event
            graph_span.add_event(
                "research_completed",
                attributes={
                    "iterations": final_state.iteration_count,
                    "source_count": len(final_state.sources),
                    "has_report": bool(final_state.final_report)
                }
            )

            # Store in memory (FR-009)
            # This creates a child span via trace_memory_operation decorator
            from src.core.memory import memory_manager
            await memory_manager.store_document(
                content=final_state.final_report,
                metadata={
                    "topic": topic,
                    "user_id": user_id,
                    "iterations": final_state.iteration_count,
                    "source_count": len(final_state.sources)
                }
            )

            graph_span.set_attribute("operation.success", True)
            return final_state.final_report

        except Exception as exc:
            graph_span.set_attribute("operation.success", False)
            graph_span.set_attribute("error_type", type(exc).__name__)
            graph_span.record_exception(exc)
            raise
```

**Windmill Integration** (in `src/windmill/daily_research.py`):
```python
from src.core.telemetry import get_tracer
from src.workflows.research_graph import execute_research_workflow

async def windmill_research_step(topic: str, user_id: str):
    """
    Windmill workflow step: Execute LangGraph research.

    Per FR-002: LangGraph executed as embedded library in Windmill step.
    Per FR-011: Emits OpenTelemetry spans for workflow start/end.
    """
    tracer = get_tracer("workflow")

    with tracer.start_as_current_span("windmill.research_step") as span:
        span.set_attribute("windmill.step_name", "research")
        span.set_attribute("workflow.topic", topic)
        span.set_attribute("workflow.user_id", user_id)
        span.set_attribute("component", "windmill")

        try:
            # Execute LangGraph (creates child spans automatically)
            result = await execute_research_workflow(topic, user_id)

            span.set_attribute("operation.success", True)
            return result

        except Exception as exc:
            span.set_attribute("operation.success", False)
            span.record_exception(exc)
            raise
```

**Expected Trace Structure**:
```
windmill.research_step (component=windmill)
└── langgraph.execution (component=workflow)
    ├── langgraph.node.plan (iteration=0)
    │   └── agent.run (component=agent)
    │       └── mcp.tool_call.search_memory (component=mcp)
    ├── langgraph.node.research (iteration=0)
    │   └── agent.run
    │       └── mcp.tool_call.web_search
    ├── langgraph.node.critique (iteration=0)
    │   └── agent.run
    ├── langgraph.edge.should_continue_research → refine
    ├── langgraph.node.refine (iteration=1)
    │   └── agent.run
    ├── langgraph.node.research (iteration=1)
    │   └── agent.run
    │       └── mcp.tool_call.web_search
    └── ... (continues for up to 5 iterations per FR-005)
```

**References**:
- Spec FR-001 through FR-015
- Plan.md sections on LangGraph structure
- Existing telemetry patterns from `src/core/telemetry.py`

---

## Summary of Decisions

| Research Question | Decision | Implementation Location |
|---|---|---|
| RQ-001: Node Spans | Custom `@trace_langgraph_node` decorator | `src/workflows/research_graph.py` |
| RQ-002: State Transitions | Custom `@trace_edge_decision` decorator + span events | `src/workflows/research_graph.py` |
| RQ-003: Cyclical Graphs | Iteration count attributes + loop exit spans | Node implementations |
| RQ-004: Windmill Correlation | Context propagation via parent spans | `src/windmill/daily_research.py` |
| RQ-005: LLM Attributes | OpenTelemetry GenAI semantic conventions + custom agent attributes | Existing `trace_agent_operation` |
| RQ-006: End-to-End Pattern | Layered decorators at workflow/node/agent/tool levels | All workflow files |

## Key Instrumentation Attributes

### Workflow-Level Spans
- `component`: "workflow" | "windmill"
- `graph.name`: "research"
- `graph.topic`: User-provided topic
- `graph.user_id`: User identifier
- `graph.final_iteration`: Total iterations
- `graph.source_count`: Number of sources found

### Node-Level Spans
- `node.name`: "plan" | "research" | "critique" | "refine" | "finish"
- `node.type`: "graph_node"
- `state.iteration_count`: Current iteration (0-based)
- `state.topic`: Research topic
- `state.status`: Current state

### Edge-Level Spans
- `edge.name`: Edge identifier
- `edge.type`: "conditional" | "static"
- `edge.next_node`: Destination node
- `state.iteration_count`: Iteration at routing time

### Agent-Level Spans (from existing `trace_agent_operation`)
- `gen_ai.system`: "pydantic_ai"
- `gen_ai.request.model`: "deepseek-v3"
- `gen_ai.usage.total_tokens`: Token consumption
- `agent.type`: "researcher"
- `agent.confidence`: 0.0-1.0
- `agent.tool_calls_count`: Number of tool invocations

### Tool-Level Spans (from existing `trace_tool_call`)
- `tool_name`: MCP tool name
- `execution_duration_ms`: Call duration
- `result_count`: Number of results
- `component`: "mcp"

### Memory-Level Spans (from existing `trace_memory_operation`)
- `operation.type`: "store_document" | "semantic_search"
- `db.system`: "postgresql"
- `component`: "memory"

## Observability Queries (Jaeger)

**View complete research workflow**:
```
service.name=paias AND component=workflow AND graph.name=research
```

**View all LangGraph nodes**:
```
service.name=paias AND node.type=graph_node
```

**View specific iteration**:
```
service.name=paias AND state.iteration_count=2
```

**View edge routing decisions**:
```
service.name=paias AND edge.type=conditional
```

**View tool calls within workflow**:
```
service.name=paias AND component=mcp AND parent.trace_id={trace_id}
```

**View workflows that hit max iterations**:
```
service.name=paias AND graph.final_iteration=5
```

## Implementation Checklist

- [ ] Create `trace_langgraph_node` decorator in `src/workflows/research_graph.py`
- [ ] Create `trace_edge_decision` decorator in `src/workflows/research_graph.py`
- [ ] Instrument all 5 nodes (plan, research, critique, refine, finish)
- [ ] Instrument conditional edge `should_continue_research`
- [ ] Add iteration tracking to state model (`ResearchState.iteration_count`)
- [ ] Create Windmill integration span in `src/windmill/daily_research.py`
- [ ] Add loop exit span for max iterations
- [ ] Test context propagation from Windmill to LangGraph
- [ ] Verify trace hierarchy in Jaeger
- [ ] Document attributes in contracts/README.md

## Open Questions

None. All technical unknowns resolved.

## Next Steps

Proceed to implementation:
1. Implement decorators in `src/workflows/research_graph.py`
2. Apply decorators to all nodes and edges
3. Test instrumentation with in-memory exporter
4. Validate trace structure in Jaeger
5. Document final attribute schema in contracts/
