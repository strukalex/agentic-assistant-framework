from __future__ import annotations

from functools import wraps
from typing import Any, Awaitable, Callable, Optional, TypeVar, cast

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

from .config import settings

T = TypeVar("T")

_provider_initialized = False
_exporter_override: Optional[SpanExporter] = None
_active_exporter: Optional[SpanExporter] = None


def _create_default_exporter() -> SpanExporter:
    """
    Build the default OTLP exporter.

    Tests can override via set_span_exporter to avoid network calls.
    """
    if settings.otel_exporter_otlp_endpoint == "memory":
        return InMemorySpanExporter()
    return OTLPSpanExporter(
        endpoint=settings.otel_exporter_otlp_endpoint, insecure=True
    )


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


def get_tracer() -> trace.Tracer:
    _init_tracer_provider()
    return trace.get_tracer("paias.memory")


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


def trace_memory_operation(
    operation_name: str,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Decorator to create a span around async memory operations with standard attributes.
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        tracer = get_tracer()

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            with tracer.start_as_current_span(f"memory.{operation_name}") as span:
                span.set_attribute("operation.type", operation_name)
                span.set_attribute("db.system", "postgresql")
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
