from __future__ import annotations

import asyncio
from functools import wraps
from typing import Any, Awaitable, Callable, Optional, TypeVar

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

from .config import settings

T = TypeVar("T")

_provider_initialized = False


def _init_tracer_provider() -> None:
    global _provider_initialized
    if _provider_initialized:
        return

    resource = Resource(attributes={"service.name": settings.otel_service_name})
    provider = TracerProvider(
        sampler=TraceIdRatioBased(settings.otel_sampling_rate),
        resource=resource,
    )
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    _provider_initialized = True


def get_tracer() -> trace.Tracer:
    _init_tracer_provider()
    return trace.get_tracer("paias.memory")


def trace_memory_operation(operation_name: str) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
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
                except Exception as exc:  # pragma: no cover - re-raised for caller handling
                    span.set_attribute("operation.success", False)
                    span.record_exception(exc)
                    raise

        return wrapper

    return decorator

