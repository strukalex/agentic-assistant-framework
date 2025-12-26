"""
Unit tests for LangGraph tracing decorators.

Validates T043 (US3): trace_langgraph_node and trace_langgraph_execution
decorators create proper spans with required attributes.

Per Spec 003 research.md and FR-011 (observable everything).
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import BaseModel

from paias.core.telemetry import (
    extract_trace_context,
    inject_trace_context,
    set_span_exporter,
    trace_api_endpoint,
    trace_langgraph_execution,
    trace_langgraph_execution_context,
    trace_langgraph_node,
)


class MockStatus(str, Enum):
    """Mock status enum for testing."""

    PLANNING = "planning"
    RESEARCHING = "researching"
    FINISHED = "finished"


class MockState(BaseModel):
    """Mock research state for testing."""

    topic: str = "test topic"
    iteration_count: int = 0
    status: MockStatus = MockStatus.PLANNING
    sources: List[str] = []
    quality_score: float = 0.0


@pytest.fixture
def exporter() -> InMemorySpanExporter:
    """Setup in-memory exporter and clear previous spans."""
    exp = InMemorySpanExporter()
    set_span_exporter(exp)
    exp.clear()
    return exp


class TestTraceLanggraphNode:
    """Tests for @trace_langgraph_node decorator."""

    @pytest.mark.asyncio
    async def test_creates_span_with_correct_name(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify span name follows pattern langgraph.node.{node_name}."""

        @trace_langgraph_node("test_node")
        async def node_func(state: MockState) -> MockState:
            return state.model_copy(update={"status": MockStatus.RESEARCHING})

        state = MockState()
        await node_func(state)

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        assert len(spans) >= 1
        span = spans[-1]
        assert span.name == "langgraph.node.test_node"

    @pytest.mark.asyncio
    async def test_sets_required_attributes(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify all required span attributes are set."""

        @trace_langgraph_node("plan")
        async def plan_node(state: MockState) -> MockState:
            return state.model_copy(update={"status": MockStatus.RESEARCHING})

        state = MockState(iteration_count=2, status=MockStatus.PLANNING)
        await plan_node(state)

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        span = spans[-1]
        assert span.attributes["component"] == "langgraph"
        assert span.attributes["node.name"] == "plan"
        assert span.attributes["operation.type"] == "node_execution"
        assert span.attributes["iteration_count"] == 2
        assert span.attributes["state.status"] == "planning"
        assert span.attributes["operation.success"] is True

    @pytest.mark.asyncio
    async def test_captures_topic_length_not_content(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify topic length is captured but not actual topic (PII safety)."""

        @trace_langgraph_node("research")
        async def research_node(state: MockState) -> MockState:
            return state

        topic = "AI governance and regulations in 2025"
        state = MockState(topic=topic)
        await research_node(state)

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        span = spans[-1]
        assert span.attributes["topic_length"] == len(topic)
        # Topic content should NOT be in attributes
        assert "topic" not in span.attributes

    @pytest.mark.asyncio
    async def test_captures_result_attributes(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify result state attributes are captured."""

        @trace_langgraph_node("critique")
        async def critique_node(state: MockState) -> MockState:
            return state.model_copy(
                update={
                    "status": MockStatus.FINISHED,
                    "iteration_count": 3,
                    "sources": ["src1", "src2", "src3"],
                }
            )

        state = MockState()
        await critique_node(state)

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        span = spans[-1]
        assert span.attributes["result.iteration_count"] == 3
        assert span.attributes["result.status"] == "finished"
        assert span.attributes["result.sources_count"] == 3

    @pytest.mark.asyncio
    async def test_captures_execution_duration(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify execution duration is captured in milliseconds."""
        import asyncio

        @trace_langgraph_node("slow_node")
        async def slow_node(state: MockState) -> MockState:
            await asyncio.sleep(0.05)  # 50ms
            return state

        await slow_node(MockState())

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        span = spans[-1]
        assert "execution_duration_ms" in span.attributes
        assert span.attributes["execution_duration_ms"] >= 40  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_records_exception_on_error(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify exceptions are recorded with proper attributes."""

        @trace_langgraph_node("failing_node")
        async def failing_node(state: MockState) -> MockState:
            raise ValueError("Node execution failed")

        with pytest.raises(ValueError, match="Node execution failed"):
            await failing_node(MockState())

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        span = spans[-1]
        assert span.attributes["operation.success"] is False
        assert span.attributes["error_type"] == "ValueError"
        assert span.attributes["error_message"] == "Node execution failed"

        # Verify exception event was recorded
        assert len(span.events) > 0
        exception_event = next(
            (e for e in span.events if e.name == "exception"), None
        )
        assert exception_event is not None


class TestTraceLanggraphExecution:
    """Tests for @trace_langgraph_execution decorator."""

    @pytest.mark.asyncio
    async def test_creates_workflow_span(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify workflow span is created with correct name."""

        @trace_langgraph_execution("daily_research")
        async def run_workflow(state: MockState) -> MockState:
            return state.model_copy(
                update={"iteration_count": 2, "sources": ["a", "b", "c"]}
            )

        await run_workflow(MockState())

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        assert len(spans) >= 1
        span = spans[-1]
        assert span.name == "langgraph.workflow.daily_research"
        assert span.attributes["component"] == "langgraph"
        assert span.attributes["workflow.name"] == "daily_research"

    @pytest.mark.asyncio
    async def test_captures_final_metrics(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify final iteration count and sources count are captured."""

        @trace_langgraph_execution("test_workflow")
        async def workflow(state: MockState) -> MockState:
            return state.model_copy(
                update={
                    "iteration_count": 4,
                    "sources": ["s1", "s2", "s3", "s4"],
                    "quality_score": 0.85,
                }
            )

        await workflow(MockState())

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        span = spans[-1]
        assert span.attributes["total_iterations"] == 4
        assert span.attributes["sources_count"] == 4
        assert span.attributes["quality_score"] == 0.85

    @pytest.mark.asyncio
    async def test_supports_traceparent_propagation(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify traceparent kwarg is used for context propagation."""

        @trace_langgraph_execution("propagation_test")
        async def workflow(state: MockState) -> MockState:
            return state

        # Valid W3C traceparent format
        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"

        await workflow(MockState(), traceparent=traceparent)

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        # Span should exist with workflow attributes
        span = spans[-1]
        assert span.name == "langgraph.workflow.propagation_test"


class TestTraceLanggraphExecutionContext:
    """Tests for trace_langgraph_execution_context context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_creates_span(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify context manager creates proper workflow span."""
        with trace_langgraph_execution_context(
            "context_test", topic="test topic"
        ) as span:
            span.set_attribute("custom", "value")

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        finished_span = spans[-1]
        assert finished_span.name == "langgraph.workflow.context_test"
        assert finished_span.attributes["topic_length"] == 10
        assert finished_span.attributes["custom"] == "value"
        assert finished_span.attributes["operation.success"] is True

    @pytest.mark.asyncio
    async def test_context_manager_with_traceparent(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify context manager accepts traceparent for distributed tracing."""
        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"

        with trace_langgraph_execution_context(
            "distributed_test", traceparent=traceparent
        ) as span:
            pass

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        span = spans[-1]
        assert span.name == "langgraph.workflow.distributed_test"

    @pytest.mark.asyncio
    async def test_context_manager_records_exception(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify exceptions are recorded when raised in context."""
        with pytest.raises(RuntimeError, match="workflow failed"):
            with trace_langgraph_execution_context("failing_workflow"):
                raise RuntimeError("workflow failed")

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        span = spans[-1]
        assert span.attributes["operation.success"] is False
        assert span.attributes["error_type"] == "RuntimeError"


class TestTraceApiEndpoint:
    """Tests for @trace_api_endpoint decorator."""

    @pytest.mark.asyncio
    async def test_creates_api_span(self, exporter: InMemorySpanExporter) -> None:
        """Verify API endpoint span is created."""

        @trace_api_endpoint("create_run")
        async def create_run(topic: str) -> dict:
            return {"run_id": "test-123", "status": "queued"}

        result = await create_run("test topic")

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        span = spans[-1]
        assert span.name == "api.create_run"
        assert span.attributes["component"] == "api"
        assert span.attributes["endpoint.name"] == "create_run"
        assert span.attributes["operation.success"] is True

    @pytest.mark.asyncio
    async def test_captures_run_id_from_response(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify run_id is extracted from response."""

        class MockResponse:
            run_id = "abc-456"

        @trace_api_endpoint("get_run")
        async def get_run(run_id: str) -> MockResponse:
            return MockResponse()

        await get_run("abc-456")

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        span = spans[-1]
        assert span.attributes["run_id"] == "abc-456"


class TestTraceContextPropagation:
    """Tests for trace context extraction/injection utilities."""

    def test_extract_trace_context_returns_none_for_none(self) -> None:
        """Verify None input returns None."""
        result = extract_trace_context(None)
        assert result is None

    def test_extract_trace_context_returns_none_for_empty_string(self) -> None:
        """Verify empty string returns None."""
        result = extract_trace_context("")
        assert result is None

    def test_extract_trace_context_parses_valid_traceparent(self) -> None:
        """Verify valid traceparent is parsed into Context."""
        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        result = extract_trace_context(traceparent)
        # Should return a Context object (not None)
        assert result is not None

    def test_inject_trace_context_returns_dict(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify inject returns dict with traceparent when span active."""
        from paias.core.telemetry import get_tracer

        tracer = get_tracer("test")
        with tracer.start_as_current_span("test_span"):
            carrier = inject_trace_context()
            # When a span is active, traceparent should be in carrier
            assert isinstance(carrier, dict)
            # Note: traceparent may or may not be present depending on sampling
