from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from src.core.config import settings
from src.core.telemetry import set_span_exporter, trace_memory_operation, trace_tool_call


@pytest.mark.asyncio
async def test_trace_memory_operation_records_success_span() -> None:
    exporter = InMemorySpanExporter()
    set_span_exporter(exporter)
    exporter.clear()

    @trace_memory_operation("unit_test")
    async def sample() -> str:
        return "ok"

    result = await sample()
    assert result == "ok"

    trace.get_tracer_provider().force_flush()
    spans = exporter.get_finished_spans()
    assert spans, "expected at least one span"
    span = spans[-1]
    assert span.name == "memory.unit_test"
    assert span.attributes["operation.type"] == "unit_test"
    assert span.attributes["operation.success"] is True
    assert span.attributes["db.system"] == "postgresql"
    assert span.resource.attributes["service.name"] == settings.otel_service_name


@pytest.mark.asyncio
async def test_trace_memory_operation_records_failure_span() -> None:
    exporter = InMemorySpanExporter()
    set_span_exporter(exporter)
    exporter.clear()

    @trace_memory_operation("failing_op")
    async def failing() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await failing()

    trace.get_tracer_provider().force_flush()
    spans = exporter.get_finished_spans()
    assert spans, "expected span even on error"
    span = spans[-1]
    assert span.attributes["operation.type"] == "failing_op"
    assert span.attributes["operation.success"] is False


# Tests for User Story 5: OpenTelemetry Observability for All Tool Calls
@pytest.mark.asyncio
async def test_trace_tool_call_decorator_creates_span_with_attributes() -> None:
    """
    T503: Verify @trace_tool_call decorator correctly creates spans
    and sets standard attributes.

    Validates FR-030: Tool invocation tracing with attributes
    """
    exporter = InMemorySpanExporter()
    set_span_exporter(exporter)
    exporter.clear()

    @trace_tool_call
    async def mock_web_search(query: str, max_results: int = 5) -> list:
        """Mock web search tool"""
        return [{"title": "Result 1", "url": "http://example.com"}]

    # Execute the tool
    result = await mock_web_search(query="test query", max_results=10)

    # Verify result
    assert result == [{"title": "Result 1", "url": "http://example.com"}]

    # Flush spans and get finished spans
    trace.get_tracer_provider().force_flush()
    spans = exporter.get_finished_spans()

    assert spans, "Expected at least one span"
    span = spans[-1]

    # Verify span name follows pattern "mcp.tool_call.{func_name}"
    assert span.name == "mcp.tool_call.mock_web_search"

    # Verify standard attributes
    assert span.attributes["tool_name"] == "mock_web_search"
    assert span.attributes["component"] == "mcp"
    assert span.attributes["operation.type"] == "tool_call"
    assert "query" in span.attributes["parameters"]
    assert span.attributes["result_count"] == 1  # List with 1 item
    assert span.attributes["operation.success"] is True


@pytest.mark.asyncio
async def test_trace_tool_call_decorator_handles_errors() -> None:
    """
    T503: Verify @trace_tool_call decorator handles errors correctly
    by setting span status to ERROR and recording exception details.

    Validates error handling per research.md RQ-004
    """
    exporter = InMemorySpanExporter()
    set_span_exporter(exporter)
    exporter.clear()

    @trace_tool_call
    async def failing_tool(param: str) -> str:
        """Tool that always fails"""
        raise ValueError("Tool execution failed")

    # Execute the tool and expect exception
    with pytest.raises(ValueError, match="Tool execution failed"):
        await failing_tool(param="test")

    # Flush spans and get finished spans
    trace.get_tracer_provider().force_flush()
    spans = exporter.get_finished_spans()

    assert spans, "Expected span even on error"
    span = spans[-1]

    # Verify span attributes for error case
    assert span.name == "mcp.tool_call.failing_tool"
    assert span.attributes["operation.success"] is False
    assert span.attributes["error_type"] == "ValueError"
    assert span.attributes["error_message"] == "Tool execution failed"

    # Verify exception was recorded
    assert len(span.events) > 0
    exception_event = next((e for e in span.events if e.name == "exception"), None)
    assert exception_event is not None


@pytest.mark.asyncio
async def test_trace_tool_call_captures_result_count() -> None:
    """
    T503: Verify @trace_tool_call decorator captures result_count
    attribute for list results.

    Validates FR-030: result_count attribute
    """
    exporter = InMemorySpanExporter()
    set_span_exporter(exporter)
    exporter.clear()

    @trace_tool_call
    async def tool_returning_list() -> list:
        """Tool that returns multiple results"""
        return ["item1", "item2", "item3", "item4", "item5"]

    # Execute the tool
    result = await tool_returning_list()
    assert len(result) == 5

    # Flush spans and verify
    trace.get_tracer_provider().force_flush()
    spans = exporter.get_finished_spans()

    span = spans[-1]
    assert span.attributes["result_count"] == 5

    # Test with non-list result
    exporter.clear()

    @trace_tool_call
    async def tool_returning_string() -> str:
        """Tool that returns single value"""
        return "single result"

    await tool_returning_string()
    trace.get_tracer_provider().force_flush()
    spans = exporter.get_finished_spans()

    span = spans[-1]
    assert span.attributes["result_count"] == 1
