"""OpenTelemetry observability setup and decorators."""

import functools
import os
from typing import Any, Callable, TypeVar

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode

# Type variable for generic decorator
F = TypeVar("F", bound=Callable[..., Any])

# Global tracer
tracer = trace.get_tracer(__name__)


def setup_opentelemetry() -> None:
    """
    Setup OpenTelemetry tracing infrastructure.

    Configures:
    - TracerProvider
    - BatchSpanProcessor
    - OTLPSpanExporter with endpoint from OTEL_EXPORTER_OTLP_ENDPOINT env var
    - Service name "paias-agent-layer"

    Per research.md RQ-004 (FR-029, FR-032)
    """
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    # Create OTLP exporter
    exporter = OTLPSpanExporter(endpoint=endpoint)

    # Create trace provider
    provider = TracerProvider()

    # Add batch processor
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # Set global tracer provider
    trace.set_tracer_provider(provider)


def trace_tool_call(func: F) -> F:
    """
    Decorator to trace MCP tool invocations with OpenTelemetry.

    Creates span with name "mcp_tool_call:{func_name}"
    Sets attributes: tool_name, parameters, result_count
    Handles errors with span.set_status(ERROR)

    Per research.md RQ-004 (FR-030)
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        span_name = f"mcp_tool_call:{func.__name__}"

        with tracer.start_as_current_span(span_name) as span:
            # Set tool name attribute
            span.set_attribute("tool_name", func.__name__)

            # Set parameters attribute (stringify for safety)
            span.set_attribute("parameters", str(kwargs))

            try:
                # Execute the tool function
                result = await func(*args, **kwargs)

                # Set result count if result is a list
                if isinstance(result, list):
                    span.set_attribute("result_count", len(result))
                else:
                    span.set_attribute("result_count", 1)

                return result

            except Exception as e:
                # Set error status
                span.set_status(Status(StatusCode.ERROR))
                span.set_attribute("error_type", type(e).__name__)
                span.set_attribute("error_message", str(e))
                raise

    return wrapper  # type: ignore[return-value]
