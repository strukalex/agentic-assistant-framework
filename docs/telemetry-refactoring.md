# Telemetry Refactoring Summary

**Date**: 2025-12-22
**Spec**: 002-researcher-agent-mcp
**Change**: Unified telemetry for memory and agent layers

## Problem

Initial implementation created duplicate OpenTelemetry setup:
- `src/core/telemetry.py` (from Spec 001 - Memory Layer)
- `src/core/observability.py` (from Spec 002 - Agent Layer)

This caused:
1. Duplicate TracerProvider initialization
2. Conflicting service names (`paias-memory-layer` vs `paias-agent-layer`)
3. Code duplication for similar decorators

## Solution: Option 1 - Unified Telemetry

**Single source of truth**: `src/core/telemetry.py`

### Changes Made

1. **DELETED** `src/core/observability.py`
2. **ENHANCED** `src/core/telemetry.py` with:
   - Updated `get_tracer(component="memory")` to support multiple components
   - Added `trace_agent_operation(operation_name)` decorator
   - Added `trace_tool_call(func)` decorator for MCP tool calls
   - Added `component` attribute to all spans
3. **UPDATED** `.env.example`:
   - Changed `OTEL_SERVICE_NAME=paias-agent-layer` → `OTEL_SERVICE_NAME=paias`

### Span Naming Convention

All operations now follow a hierarchical naming:

```
Service: paias
├── Component: memory
│   ├── memory.store_document
│   ├── memory.semantic_search
│   ├── memory.get_conversation_history
│   └── memory.temporal_query
├── Component: agent
│   └── agent.run
└── Component: mcp
    ├── mcp.tool_call.web_search
    ├── mcp.tool_call.read_file
    ├── mcp.tool_call.get_current_time
    ├── mcp.tool_call.search_memory
    └── mcp.tool_call.store_memory
```

### Standard Span Attributes

All decorators now set:
- `component`: "memory" | "agent" | "mcp"
- `operation.type`: The operation name
- `operation.success`: true | false

**Memory operations** additionally set:
- `db.system`: "postgresql"

**MCP tool calls** additionally set:
- `tool_name`: The tool function name
- `parameters`: Stringified kwargs
- `result_count`: Number of results

### Usage Examples

#### Memory Operations (existing - unchanged)
```python
from src.core.telemetry import trace_memory_operation

@trace_memory_operation("store_document")
async def store_document(self, content: str, metadata: dict) -> UUID:
    ...
```

#### Agent Operations (new)
```python
from src.core.telemetry import trace_agent_operation

@trace_agent_operation("run")
async def run_agent(task: str) -> AgentResponse:
    ...
```

#### MCP Tool Calls (new)
```python
from src.core.telemetry import trace_tool_call

@trace_tool_call
async def web_search(ctx: RunContext, query: str) -> list:
    ...
```

## Benefits

1. **Single initialization**: No conflicting TracerProvider setup
2. **Unified service**: All traces appear under `paias` service in Jaeger
3. **Component filtering**: Can filter by `component` attribute in Jaeger queries
4. **Code reuse**: Shared initialization and exporter logic
5. **Test compatibility**: Existing test infrastructure works for all components
6. **Simpler config**: One `OTEL_SERVICE_NAME` variable

## Jaeger Query Examples

View all memory operations:
```
service.name=paias AND component=memory
```

View all MCP tool calls:
```
service.name=paias AND component=mcp
```

View all agent runs:
```
service.name=paias AND component=agent
```

View specific tool:
```
service.name=paias AND tool_name=web_search
```

## Migration Notes

For future implementations:
- **Always import from** `src.core.telemetry` (not observability)
- **Use appropriate decorator**:
  - Memory operations: `@trace_memory_operation("operation_name")`
  - Agent operations: `@trace_agent_operation("operation_name")`
  - MCP tool calls: `@trace_tool_call`
- **Service name**: Always use `paias` (covers all components)
