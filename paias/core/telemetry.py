from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Awaitable, Callable, Iterator, Optional, TypeVar, Union, cast

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from .config import settings

T = TypeVar("T")

_provider_initialized = False
_exporter_override: Optional[SpanExporter] = None
_active_exporter: Optional[SpanExporter] = None
_logging_initialized = False


def _create_default_exporter() -> SpanExporter:
    """
    Build the default OTLP exporter.

    Tests can override via set_span_exporter to avoid network calls.
    Uses InMemorySpanExporter if endpoint is "memory" or "disabled".
    """
    import os
    import logging

    logger = logging.getLogger(__name__)

    # Check environment variable directly (Windmill may set this)
    endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT", settings.otel_exporter_otlp_endpoint
    )

    if endpoint in ("memory", "disabled", "none", ""):
        logger.info("Telemetry: Using in-memory exporter (endpoint=%s)", endpoint)
        return InMemorySpanExporter()

    logger.info("Telemetry: Using OTLP exporter at %s", endpoint)
    return OTLPSpanExporter(endpoint=endpoint, insecure=True)


def _init_tracer_provider(exporter: Optional[SpanExporter] = None) -> None:
    global _provider_initialized, _active_exporter
    if _provider_initialized:
        return

    resource = Resource(attributes={"service.name": settings.otel_service_name})
    provider = TracerProvider(
        sampler=TraceIdRatioBased(settings.otel_sampling_rate),
        resource=resource,
    )
    resolved_exporter = exporter or _exporter_override or _create_default_exporter()
    processor = BatchSpanProcessor(resolved_exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    _active_exporter = resolved_exporter
    _provider_initialized = True

    # Also initialize OTLP logging if configured
    _init_otlp_logging()


def _init_otlp_logging() -> None:
    """
    Initialize OTLP log export to Loki if OTEL_EXPORTER_OTLP_LOGS_ENDPOINT is configured.

    This sets up Python's logging to export logs via OTLP to Loki or another
    OTLP-compatible log backend.
    """
    global _logging_initialized
    if _logging_initialized:
        return

    import os

    # Use print for early diagnostics since logger may not be configured yet
    print("=== OTLP LOGGING DIAGNOSTICS ===")
    print(f"_logging_initialized: {_logging_initialized}")

    # Check all OTEL-related env vars for debugging
    otel_env_vars = {k: v for k, v in os.environ.items() if k.startswith("OTEL")}
    print(f"OTEL environment variables: {otel_env_vars}")

    # Check environment variable directly (Windmill may set this)
    logs_endpoint_env = os.environ.get("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT")
    logs_endpoint_settings = settings.otel_exporter_otlp_logs_endpoint
    logs_endpoint = logs_endpoint_env or logs_endpoint_settings

    print(f"OTEL_EXPORTER_OTLP_LOGS_ENDPOINT from env: {logs_endpoint_env}")
    print(f"otel_exporter_otlp_logs_endpoint from settings: {logs_endpoint_settings}")
    print(f"Resolved logs_endpoint: {logs_endpoint}")

    if not logs_endpoint:
        print("OTLP logging: No logs endpoint configured, skipping")
        print("=== END OTLP LOGGING DIAGNOSTICS ===")
        return

    try:
        print("Attempting to import OTLP logging components...")
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

        print("Imports successful")

        resource = Resource(attributes={"service.name": settings.otel_service_name})
        print(f"Created resource with service.name: {settings.otel_service_name}")

        # Create logger provider with OTLP HTTP exporter (Loki uses HTTP)
        logger_provider = LoggerProvider(resource=resource)
        print("Created LoggerProvider")

        # Use HTTP exporter for Loki compatibility
        log_exporter = OTLPLogExporter(endpoint=logs_endpoint)
        print(f"Created OTLPLogExporter with endpoint: {logs_endpoint}")

        logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
        print("Added BatchLogRecordProcessor")

        set_logger_provider(logger_provider)
        print("Set logger provider")

        # Attach OTLP handler to root logger so all Python logs are exported
        handler = LoggingHandler(
            level=logging.DEBUG, logger_provider=logger_provider
        )
        logging.getLogger().addHandler(handler)
        print("Added LoggingHandler to root logger")

        _logging_initialized = True
        print(f"OTLP logging: Initialized successfully, exporting to {logs_endpoint}")
        print("=== END OTLP LOGGING DIAGNOSTICS ===")

        # Also log via the logger now that it's set up
        logger = logging.getLogger(__name__)
        logger.info("OTLP logging: Initialized, exporting to %s", logs_endpoint)

    except ImportError as e:
        print(f"OTLP logging: Import error: {e}")
        print("=== END OTLP LOGGING DIAGNOSTICS ===")
        logger = logging.getLogger(__name__)
        logger.warning(
            "OTLP logging: Failed to import logging SDK components: %s. "
            "Logs will not be exported to Loki.",
            e,
        )
    except Exception as e:
        print(f"OTLP logging: Exception: {e}")
        import traceback
        traceback.print_exc()
        print("=== END OTLP LOGGING DIAGNOSTICS ===")
        logger = logging.getLogger(__name__)
        logger.warning(
            "OTLP logging: Failed to initialize: %s. Logs will not be exported to Loki.",
            e,
        )


def get_tracer(component: str = "memory") -> trace.Tracer:
    """
    Get a tracer for the specified component.

    Args:
        component: Component name (e.g., "memory", "agent", "mcp")

    Returns:
        OpenTelemetry Tracer instance
    """
    _init_tracer_provider()
    return trace.get_tracer(f"paias.{component}")


def set_span_exporter(exporter: SpanExporter) -> SpanExporter:
    """
    Override the exporter (useful for tests with InMemorySpanExporter).
    """
    global _exporter_override, _provider_initialized, _active_exporter
    _exporter_override = exporter
    if _provider_initialized:
        provider = cast(TracerProvider, trace.get_tracer_provider())
        provider.add_span_processor(BatchSpanProcessor(exporter))
        _active_exporter = exporter
    else:
        _init_tracer_provider(exporter=exporter)
    _provider_initialized = True
    return exporter


def get_active_span_exporter() -> Optional[SpanExporter]:
    """Return the exporter currently wired into the tracer provider."""
    return _active_exporter


def init_telemetry() -> None:
    """
    Initialize all telemetry: tracing and OTLP logging.

    Call this early in application startup to ensure logs are exported
    to Loki from the very beginning.
    """
    _init_tracer_provider()
    # _init_otlp_logging() is called by _init_tracer_provider


def trace_memory_operation(
    operation_name: str,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Decorator to create a span around async memory operations with standard attributes.
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        tracer = get_tracer("memory")

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            with tracer.start_as_current_span(f"memory.{operation_name}") as span:
                span.set_attribute("operation.type", operation_name)
                span.set_attribute("db.system", "postgresql")
                span.set_attribute("component", "memory")
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("operation.success", True)
                    return result
                except (
                    Exception
                ) as exc:  # pragma: no cover - re-raised for caller handling
                    span.set_attribute("operation.success", False)
                    span.record_exception(exc)
                    raise

        return wrapper

    return decorator


def trace_agent_operation(
    operation_name: str,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Decorator to create a span around async agent operations with standard attributes.

    Usage:
        @trace_agent_operation("run")
        async def run_agent(...):
            ...
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        tracer = get_tracer("agent")

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            with tracer.start_as_current_span(f"agent.{operation_name}") as span:
                span.set_attribute("operation.type", operation_name)
                span.set_attribute("component", "agent")
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


def trace_tool_call(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """
    Decorator to trace MCP tool invocations with OpenTelemetry.

    Creates span with name "mcp.tool_call.{func_name}"
    Sets attributes: tool_name, parameters, result_count, execution_duration_ms,
    component
    Handles errors with span.record_exception()

    Per Spec 002 research.md RQ-004 (FR-030)
    Per Spec 002 tasks.md T504: Captures execution_duration_ms

    Usage:
        @trace_tool_call
        async def web_search(...):
            ...
    """
    import time

    tracer = get_tracer("mcp")

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        span_name = f"mcp.tool_call.{func.__name__}"

        with tracer.start_as_current_span(span_name) as span:
            # Set standard attributes
            span.set_attribute("tool_name", func.__name__)
            span.set_attribute("component", "mcp")
            span.set_attribute("operation.type", "tool_call")

            # Set parameters attribute (stringify for safety)
            span.set_attribute("parameters", str(kwargs))

            # T504: Capture execution start time
            start_time = time.perf_counter()

            try:
                # Execute the tool function
                result = await func(*args, **kwargs)

                # T504: Calculate and set execution duration in milliseconds
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                span.set_attribute("execution_duration_ms", duration_ms)

                # Set result count if result is a list
                if isinstance(result, list):
                    span.set_attribute("result_count", len(result))
                else:
                    span.set_attribute("result_count", 1)

                span.set_attribute("operation.success", True)
                return result

            except Exception as exc:
                # T504: Calculate duration even on error
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                span.set_attribute("execution_duration_ms", duration_ms)

                # Record exception and set error attributes
                span.set_attribute("operation.success", False)
                span.set_attribute("error_type", type(exc).__name__)
                span.set_attribute("error_message", str(exc))
                span.record_exception(exc)
                raise

    return wrapper


# W3C Trace Context propagation utilities
_propagator = TraceContextTextMapPropagator()


def extract_trace_context(traceparent: Optional[str]) -> Optional[Context]:
    """
    Extract OpenTelemetry context from a W3C traceparent header.

    Args:
        traceparent: W3C traceparent header value (e.g., "00-traceid-spanid-01")

    Returns:
        OpenTelemetry Context if valid, None otherwise.
    """
    if not traceparent:
        return None
    carrier = {"traceparent": traceparent}
    return _propagator.extract(carrier)


def inject_trace_context() -> dict[str, str]:
    """
    Inject current trace context into a carrier dict for propagation.

    Returns:
        Dict containing traceparent header if a span is active.
    """
    carrier: dict[str, str] = {}
    _propagator.inject(carrier)
    return carrier


# LangGraph tracing decorators per Spec 003 research.md


def trace_langgraph_node(
    node_name: str,
) -> Callable[
    [Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]
]:
    """
    Decorator for tracing LangGraph node execution.

    Creates a span for each node invocation with attributes:
    - component: "langgraph"
    - node.name: The node identifier
    - iteration_count: Current iteration (from state if available)
    - state.status: Current state status (from state if available)

    Per Spec 003 research.md and FR-011 (observable everything).

    Usage:
        @trace_langgraph_node("plan")
        async def plan_node(state: ResearchState) -> ResearchState:
            ...
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        tracer = get_tracer("langgraph")

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            span_name = f"langgraph.node.{node_name}"

            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("component", "langgraph")
                span.set_attribute("node.name", node_name)
                span.set_attribute("operation.type", "node_execution")

                # Extract state attributes if first positional arg is state-like
                state = args[0] if args else None
                if state is not None:
                    if hasattr(state, "iteration_count"):
                        span.set_attribute(
                            "iteration_count", getattr(state, "iteration_count", 0)
                        )
                    if hasattr(state, "status"):
                        status = getattr(state, "status", None)
                        if hasattr(status, "value"):
                            span.set_attribute("state.status", status.value)
                        elif status is not None:
                            span.set_attribute("state.status", str(status))
                    if hasattr(state, "topic"):
                        topic = getattr(state, "topic", "")
                        span.set_attribute("topic_length", len(str(topic)))

                start_time = time.perf_counter()

                try:
                    result = await func(*args, **kwargs)

                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    span.set_attribute("execution_duration_ms", duration_ms)
                    span.set_attribute("operation.success", True)

                    # Capture result state attributes
                    if hasattr(result, "iteration_count"):
                        span.set_attribute(
                            "result.iteration_count",
                            getattr(result, "iteration_count", 0),
                        )
                    if hasattr(result, "status"):
                        status = getattr(result, "status", None)
                        if hasattr(status, "value"):
                            span.set_attribute("result.status", status.value)
                        elif status is not None:
                            span.set_attribute("result.status", str(status))
                    if hasattr(result, "sources"):
                        sources = getattr(result, "sources", [])
                        span.set_attribute("result.sources_count", len(sources))

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

    return decorator


@contextmanager
def trace_langgraph_execution_context(
    workflow_name: str,
    topic: Optional[str] = None,
    traceparent: Optional[str] = None,
) -> Iterator[trace.Span]:
    """
    Context manager for tracing full LangGraph workflow execution.

    Creates a root span for the entire workflow with attributes:
    - component: "langgraph"
    - workflow.name: Workflow identifier
    - topic_length: Length of topic string (avoid storing PII)

    Supports distributed tracing by linking to parent context from traceparent.

    Per Spec 003 research.md and FR-011 (observable everything).

    Usage:
        with trace_langgraph_execution_context("daily_research", topic=topic) as span:
            result = await graph.ainvoke(initial_state)
            span.set_attribute("total_iterations", result.iteration_count)
    """
    tracer = get_tracer("langgraph")
    span_name = f"langgraph.workflow.{workflow_name}"

    # Extract parent context if traceparent provided
    parent_context = extract_trace_context(traceparent)

    with tracer.start_as_current_span(
        span_name, context=parent_context
    ) as span:
        span.set_attribute("component", "langgraph")
        span.set_attribute("workflow.name", workflow_name)
        span.set_attribute("operation.type", "workflow_execution")

        if topic:
            span.set_attribute("topic_length", len(topic))

        start_time = time.perf_counter()

        try:
            yield span
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            span.set_attribute("execution_duration_ms", duration_ms)
            span.set_attribute("operation.success", True)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            span.set_attribute("execution_duration_ms", duration_ms)
            span.set_attribute("operation.success", False)
            span.set_attribute("error_type", type(exc).__name__)
            span.set_attribute("error_message", str(exc))
            span.record_exception(exc)
            raise


def trace_langgraph_execution(
    workflow_name: str,
) -> Callable[
    [Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]
]:
    """
    Decorator for tracing full LangGraph workflow execution.

    Creates a root span for the entire workflow with attributes:
    - component: "langgraph"
    - workflow.name: Workflow identifier
    - topic_length: Length of topic string (avoid storing PII)
    - total_iterations: Final iteration count (if available on result)
    - sources_count: Number of sources collected (if available on result)

    Per Spec 003 research.md and FR-011 (observable everything).

    Usage:
        @trace_langgraph_execution("daily_research")
        async def run_research_workflow(state: ResearchState) -> ResearchState:
            ...
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        tracer = get_tracer("langgraph")

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            span_name = f"langgraph.workflow.{workflow_name}"

            # Check for traceparent in kwargs for distributed tracing
            traceparent = kwargs.pop("traceparent", None)
            parent_context = extract_trace_context(traceparent)

            with tracer.start_as_current_span(
                span_name, context=parent_context
            ) as span:
                span.set_attribute("component", "langgraph")
                span.set_attribute("workflow.name", workflow_name)
                span.set_attribute("operation.type", "workflow_execution")

                # Extract topic from first arg if state-like
                state = args[0] if args else None
                if state is not None and hasattr(state, "topic"):
                    topic = getattr(state, "topic", "")
                    span.set_attribute("topic_length", len(str(topic)))

                start_time = time.perf_counter()

                try:
                    result = await func(*args, **kwargs)

                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    span.set_attribute("execution_duration_ms", duration_ms)
                    span.set_attribute("operation.success", True)

                    # Capture final metrics from result
                    if hasattr(result, "iteration_count"):
                        span.set_attribute(
                            "total_iterations", getattr(result, "iteration_count", 0)
                        )
                    if hasattr(result, "sources"):
                        sources = getattr(result, "sources", [])
                        span.set_attribute("sources_count", len(sources))
                    if hasattr(result, "quality_score"):
                        try:
                            span.set_attribute(
                                "quality_score",
                                float(getattr(result, "quality_score", 0.0)),
                            )
                        except (TypeError, ValueError):
                            pass

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

    return decorator


def trace_api_endpoint(
    endpoint_name: str,
) -> Callable[
    [Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]
]:
    """
    Decorator for tracing API endpoint execution.

    Creates a span for each API request with attributes:
    - component: "api"
    - endpoint.name: The endpoint identifier
    - http.method: HTTP method (extracted from request if available)

    Per Spec 003 FR-011 (observable everything).

    Usage:
        @trace_api_endpoint("create_run")
        async def create_run(payload: CreateRunRequest) -> CreateRunResponse:
            ...
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        tracer = get_tracer("api")

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            span_name = f"api.{endpoint_name}"

            # Check for client_traceparent in payload for distributed tracing
            traceparent = None
            payload = kwargs.get("payload") or (args[0] if args else None)
            if payload is not None and hasattr(payload, "client_traceparent"):
                traceparent = getattr(payload, "client_traceparent", None)

            parent_context = extract_trace_context(traceparent)

            with tracer.start_as_current_span(
                span_name, context=parent_context
            ) as span:
                span.set_attribute("component", "api")
                span.set_attribute("endpoint.name", endpoint_name)
                span.set_attribute("operation.type", "api_request")

                start_time = time.perf_counter()

                try:
                    result = await func(*args, **kwargs)

                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    span.set_attribute("execution_duration_ms", duration_ms)
                    span.set_attribute("operation.success", True)

                    # Capture run_id from response if available
                    if hasattr(result, "run_id"):
                        span.set_attribute("run_id", str(getattr(result, "run_id")))

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

    return decorator
