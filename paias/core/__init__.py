"""Core utilities for PAIAS.

Exports:
    init_telemetry: Initialize tracing and OTLP logging
    get_tracer: Get an OpenTelemetry tracer
    settings: Application settings
"""
from .telemetry import get_tracer, init_telemetry
from .config import settings

__all__ = ["get_tracer", "init_telemetry", "settings"]
