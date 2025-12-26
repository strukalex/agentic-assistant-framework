# ruff: noqa
"""
Integration tests for OpenTelemetry observability.

Validates that all ResearcherAgent operations are fully instrumented with
OpenTelemetry tracing, including MCP tool calls and agent.run() invocations.

Per Spec 002 tasks.md Phase 7 (User Story 5): T500-T502
"""

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from paias.core.config import settings
from paias.core.telemetry import set_span_exporter


@pytest.mark.asyncio
class TestOpenTelemetryConfiguration:
    """Validate OpenTelemetry exporter configuration (T500)."""

    async def test_otel_exporter_configured_with_endpoint_from_env(self):
        """
        T500: Verify OpenTelemetry exporter is configured with OTLP endpoint
        from OTEL_EXPORTER_OTLP_ENDPOINT environment variable.

        Validates FR-029, FR-032: OTLP exporter configuration
        """
        # Verify settings loaded from environment
        assert settings.otel_exporter_otlp_endpoint is not None
        assert settings.otel_service_name is not None

        # Expected service name from Constitution Article II.H
        assert settings.otel_service_name == "paias"

        # Verify exporter can be initialized
        # (using in-memory for tests, but endpoint config is validated)
        exporter = InMemorySpanExporter()
        set_span_exporter(exporter)

        # Create a test span to verify exporter works
        from paias.core.telemetry import get_tracer

        tracer = get_tracer("test")
        with tracer.start_as_current_span("test_span") as span:
            span.set_attribute("test", "value")

        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        assert len(spans) > 0
        span = spans[-1]
        assert span.name == "test_span"
        assert span.resource.attributes["service.name"] == "paias"


@pytest.mark.asyncio
class TestMCPToolInvocationTracing:
    """Validate MCP tool invocations create trace spans (T501)."""

    async def test_mcp_tool_invocations_create_trace_spans_with_attributes(
        self, mock_memory_manager
    ):
        """
        T501: Verify all MCP tool invocations create trace spans with
        required attributes: tool_name, parameters, result_count, execution_duration_ms.

        Validates FR-030: MCP tool invocation tracing
        """
        # Setup in-memory exporter for testing
        exporter = InMemorySpanExporter()
        set_span_exporter(exporter)
        exporter.clear()

        # Import and call a traced tool directly (bypassing RunContext)
        from paias.agents.researcher import search_memory
        from unittest.mock import MagicMock

        # Create a minimal mock RunContext-like object
        ctx = MagicMock()
        ctx.deps = mock_memory_manager

        result = await search_memory(ctx, query="test query")

        # Verify tool executed
        assert result is not None

        # Flush spans and verify
        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        assert len(spans) > 0
        span = spans[-1]

        # Verify span attributes per FR-030
        assert span.name == "mcp.tool_call.search_memory"
        assert span.attributes["tool_name"] == "search_memory"
        assert span.attributes["component"] == "mcp"
        assert "parameters" in span.attributes

        # Result count should be present
        assert "result_count" in span.attributes

        # Verify execution_duration_ms is captured (T504)
        assert "execution_duration_ms" in span.attributes


@pytest.mark.asyncio
class TestAgentRunTracing:
    """Validate agent.run() calls create trace spans (T502)."""

    @pytest.mark.skip(reason="Requires Azure AI API - skipping to avoid rate limits")
    async def test_agent_run_creates_trace_spans_with_all_attributes(
        self, mock_memory_manager
    ):
        """
        T502: Verify agent.run() calls create trace spans with all required
        attributes: confidence_score, tool_calls_count, task_description, result_type.

        Validates FR-031: Agent execution tracing
        """
        # Setup in-memory exporter
        exporter = InMemorySpanExporter()
        set_span_exporter(exporter)
        exporter.clear()

        # Import and execute agent
        from paias.agents.researcher import researcher_agent, run_agent_with_tracing

        task = "What is the capital of France?"

        # Execute agent with tracing
        result = await run_agent_with_tracing(
            agent=researcher_agent,
            task=task,
            deps=mock_memory_manager,
            mcp_session=None,
        )

        # Verify result
        assert result is not None

        # Flush spans and verify
        trace.get_tracer_provider().force_flush()
        spans = exporter.get_finished_spans()

        # Find the agent_run span
        agent_run_span = next((s for s in spans if s.name == "agent_run"), None)
        assert agent_run_span is not None, "agent_run span should exist"

        # Verify required attributes per FR-031
        assert agent_run_span.attributes["task_description"] == task
        assert "result_type" in agent_run_span.attributes
        assert agent_run_span.attributes["result_type"] in [
            "AgentResponse",
            "ToolGapReport",
        ]

        # If result is AgentResponse, verify confidence_score and tool_calls_count
        if agent_run_span.attributes["result_type"] == "AgentResponse":
            assert "confidence_score" in agent_run_span.attributes
            assert "tool_calls_count" in agent_run_span.attributes


@pytest.fixture
def mock_memory_manager():
    """Provide a mock MemoryManager for testing."""
    from unittest.mock import AsyncMock, MagicMock

    mock = MagicMock()

    # Mock past research result
    past_research = type(
        "Document",
        (),
        {
            "content": "Paris is the capital of France",
            "metadata_": {"topic": "geography", "timestamp": "2025-12-15"},
        },
    )()

    mock.semantic_search = AsyncMock(return_value=[past_research])
    mock.store_document = AsyncMock(return_value="doc_test_456")

    return mock
