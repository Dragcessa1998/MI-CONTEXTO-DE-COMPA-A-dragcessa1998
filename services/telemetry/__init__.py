"""Análisis de telemetría operacional de Nexova."""

from .analysis import (
    SupabaseTelemetryReader,
    auth_failure_rate,
    error_rate_by_type,
    events_per_day,
    latency_by_route,
)

__all__ = [
    "SupabaseTelemetryReader",
    "auth_failure_rate",
    "error_rate_by_type",
    "events_per_day",
    "latency_by_route",
]
