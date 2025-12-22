from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from src.core.config import settings
from src.core.telemetry import set_span_exporter, trace_memory_operation


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

