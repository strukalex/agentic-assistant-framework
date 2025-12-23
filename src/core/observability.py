"""OpenTelemetry observability infrastructure for agent layer.

Provides tracing setup and decorators for instrumenting agent operations
and MCP tool calls.

Per Spec 002 research.md RQ-004 (FR-029, FR-030, FR-031, FR-032)
"""

import os
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

T = TypeVar("T")

# Service name for agent layer (per spec.md FR-029)
SERVICE_NAME = "paias-agent-layer"

# Initialize tracer provider if not already initialized
_provider_initialized = False


def _init_tracer_provider() -> None:
    """Initialize OpenTelemetry tracer provider with OTLP exporter.

    Configures TracerProvider with BatchSpanProcessor and OTLPSpanExporter.
    Endpoint is read from OTEL_EXPORTER_OTLP_ENDPOINT env var.
    Service name is "paias-agent-layer" per spec.md FR-029.

    Per research.md RQ-004 (FR-029, FR-032)
    """
    global _provider_initialized
    if _provider_initialized:
        return

    endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
    )

    resource = Resource(attributes={"service.name": SERVICE_NAME})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)
    _provider_initialized = True


def get_tracer(component: str = "agent") -> trace.Tracer:
    """Get a tracer for the specified component.

    Args:
        component: Component name (e.g., "agent", "mcp")

    Returns:
        OpenTelemetry Tracer instance
    """
    _init_tracer_provider()
    return trace.get_tracer(f"{SERVICE_NAME}.{component}")


def trace_tool_call(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """Decorator to trace MCP tool invocations with OpenTelemetry.

    Creates span with name "mcp_tool_call:{func_name}".
    Sets attributes: tool_name, parameters, result_count, execution_duration_ms.
    Handles errors with span.set_status(ERROR).

    Per research.md RQ-004 (FR-030)

    Usage:
        @trace_tool_call
        async def web_search(query: str):
            ...
    """
    tracer = get_tracer("mcp")

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        import time

        span_name = f"mcp_tool_call:{func.__name__}"
        start_time = time.perf_counter()

        with tracer.start_as_current_span(span_name) as span:
            # Set standard attributes
            span.set_attribute("tool_name", func.__name__)
            span.set_attribute("parameters", str(kwargs))

            try:
                # Execute the tool function
                result = await func(*args, **kwargs)

                # Calculate execution duration
                duration_ms = (time.perf_counter() - start_time) * 1000
                span.set_attribute("execution_duration_ms", round(duration_ms, 2))

                # Set result count if result is a list
                if isinstance(result, list):
                    span.set_attribute("result_count", len(result))
                else:
                    span.set_attribute("result_count", 1)

                return result

            except Exception as exc:
                # Set error status and attributes
                span.set_status(Status(StatusCode.ERROR))
                span.set_attribute("error_type", type(exc).__name__)
                span.set_attribute("error_message", str(exc))
                span.record_exception(exc)
                raise

    return wrapper

