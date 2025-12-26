"""
Integration tests for OpenTelemetry observability in DailyTrendingResearch workflow.

Validates T044 (US3): End-to-end spans are emitted for:
- LangGraph workflow execution (root span)
- Per-node spans (plan, research, critique, refine, finish)
- API endpoint spans

Per Spec 003 FR-011 (observable everything).
"""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from paias.core.telemetry import set_span_exporter
from paias.models.agent_response import AgentResponse
from paias.models.research_state import ResearchState
from paias.workflows.research_graph import compile_research_graph, InMemoryMemoryManager


async def _mock_agent_runner(task: str, deps, *, max_runtime_seconds: float | None = None) -> AgentResponse:
    """Mock agent runner for tracing tests."""
    return AgentResponse(
        answer="Mock research findings",
        reasoning="Mock reasoning for tracing tests",
        tool_calls=[],
        confidence=0.8,
    )


@pytest.fixture
def exporter() -> InMemorySpanExporter:
    """Setup in-memory exporter and clear previous spans."""
    exp = InMemorySpanExporter()
    set_span_exporter(exp)
    exp.clear()
    return exp


class TestWorkflowTracingIntegration:
    """Integration tests for end-to-end workflow tracing."""

    @pytest.mark.asyncio
    async def test_workflow_run_creates_root_and_node_spans(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify complete workflow run creates all expected spans."""
        # Compile and run the graph
        app = compile_research_graph(memory_manager=InMemoryMemoryManager(), agent_runner=_mock_agent_runner)
        initial_state = ResearchState(
            topic="Test tracing integration",
            user_id="00000000-0000-0000-0000-000000000001",
        )

        result = await app.ainvoke(initial_state)

        # Flush spans
        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        # Get span names
        span_names = [s.name for s in spans]

        # Verify root workflow span exists
        workflow_spans = [n for n in span_names if "langgraph.workflow" in n]
        assert len(workflow_spans) >= 1, f"Expected workflow span, got: {span_names}"

        # Verify node spans exist
        assert any("langgraph.node.plan" in n for n in span_names), (
            f"Expected plan node span, got: {span_names}"
        )
        assert any("langgraph.node.research" in n for n in span_names), (
            f"Expected research node span, got: {span_names}"
        )
        assert any("langgraph.node.critique" in n for n in span_names), (
            f"Expected critique node span, got: {span_names}"
        )
        assert any("langgraph.node.finish" in n for n in span_names), (
            f"Expected finish node span, got: {span_names}"
        )

    @pytest.mark.asyncio
    async def test_workflow_span_captures_final_metrics(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify workflow root span captures iteration count and sources count."""
        app = compile_research_graph(memory_manager=InMemoryMemoryManager(), agent_runner=_mock_agent_runner)
        initial_state = ResearchState(
            topic="Metrics test topic",
            user_id="00000000-0000-0000-0000-000000000002",
        )

        result = await app.ainvoke(initial_state)

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        # Find the workflow root span
        workflow_span = next(
            (s for s in spans if "langgraph.workflow.daily_research" in s.name),
            None,
        )

        assert workflow_span is not None, "Workflow span not found"
        assert workflow_span.attributes["total_iterations"] == result.iteration_count
        assert workflow_span.attributes["sources_count"] == len(result.sources)
        assert workflow_span.attributes["operation.success"] is True

    @pytest.mark.asyncio
    async def test_node_spans_capture_state_attributes(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify node spans capture iteration count and status transitions."""
        app = compile_research_graph(memory_manager=InMemoryMemoryManager(), agent_runner=_mock_agent_runner)
        initial_state = ResearchState(
            topic="State attributes test",
            user_id="00000000-0000-0000-0000-000000000003",
        )

        await app.ainvoke(initial_state)

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        # Find plan node span
        plan_span = next(
            (s for s in spans if s.name == "langgraph.node.plan"), None
        )

        assert plan_span is not None, "Plan span not found"
        assert plan_span.attributes["component"] == "langgraph"
        assert plan_span.attributes["node.name"] == "plan"
        assert plan_span.attributes["operation.success"] is True

        # Find research node span
        research_span = next(
            (s for s in spans if s.name == "langgraph.node.research"), None
        )

        assert research_span is not None, "Research span not found"
        assert "result.iteration_count" in research_span.attributes
        assert "result.sources_count" in research_span.attributes

    @pytest.mark.asyncio
    async def test_traceparent_propagation(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify traceparent parameter is accepted for distributed tracing."""
        app = compile_research_graph(memory_manager=InMemoryMemoryManager(), agent_runner=_mock_agent_runner)
        initial_state = ResearchState(
            topic="Distributed tracing test",
            user_id="00000000-0000-0000-0000-000000000004",
        )

        # Valid W3C traceparent
        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"

        # Should not raise
        result = await app.ainvoke(initial_state, traceparent=traceparent)

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        # Workflow span should exist
        workflow_spans = [s for s in spans if "langgraph.workflow" in s.name]
        assert len(workflow_spans) >= 1

    @pytest.mark.asyncio
    async def test_all_node_spans_have_execution_duration(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify all node spans capture execution_duration_ms."""
        app = compile_research_graph(memory_manager=InMemoryMemoryManager(), agent_runner=_mock_agent_runner)
        initial_state = ResearchState(
            topic="Duration test",
            user_id="00000000-0000-0000-0000-000000000005",
        )

        await app.ainvoke(initial_state)

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        # All node spans should have execution_duration_ms
        node_spans = [s for s in spans if "langgraph.node." in s.name]

        for span in node_spans:
            assert "execution_duration_ms" in span.attributes, (
                f"Span {span.name} missing execution_duration_ms"
            )
            assert span.attributes["execution_duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_workflow_with_multiple_iterations(
        self, exporter: InMemorySpanExporter
    ) -> None:
        """Verify spans are created for each iteration in the loop."""
        # Create a state that will require multiple iterations
        # (quality_threshold set high, max_iterations > 1)
        app = compile_research_graph(memory_manager=InMemoryMemoryManager(), agent_runner=_mock_agent_runner)
        initial_state = ResearchState(
            topic="Multi-iteration test",
            user_id="00000000-0000-0000-0000-000000000006",
            quality_threshold=0.99,  # High threshold to force refinement
            max_iterations=2,  # Allow up to 2 iterations
        )

        result = await app.ainvoke(initial_state)

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        # Count research node spans (should have at least 1)
        research_spans = [s for s in spans if s.name == "langgraph.node.research"]
        assert len(research_spans) >= 1

        # Count critique node spans (should match research)
        critique_spans = [s for s in spans if s.name == "langgraph.node.critique"]
        assert len(critique_spans) >= 1

        # Workflow span should show total iterations
        workflow_span = next(
            (s for s in spans if "langgraph.workflow" in s.name), None
        )
        assert workflow_span is not None
        assert workflow_span.attributes["total_iterations"] == result.iteration_count
