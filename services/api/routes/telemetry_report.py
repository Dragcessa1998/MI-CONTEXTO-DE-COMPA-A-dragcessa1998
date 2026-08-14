"""Endpoint cacheado para métricas técnicas de telemetría."""

from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from telemetry.analysis import (
    SupabaseTelemetryReader,
    TelemetryReader,
    auth_failure_rate,
    error_rate_by_type,
    events_per_day,
    latency_by_route,
)


router = APIRouter(prefix="/telemetry", tags=["telemetry"])
reader: TelemetryReader = SupabaseTelemetryReader()
CACHE_TTL_SECONDS = 60
_report_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
_cache_lock = Lock()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _cache_key(start_date: datetime | None, end_date: datetime | None) -> tuple[str, str]:
    return (
        _as_utc(start_date).isoformat() if start_date else "default",
        _as_utc(end_date).isoformat() if end_date else "default",
    )


def _iso_z(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


@router.get("/report")
def telemetry_report(
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
) -> dict[str, Any]:
    """Sirve el mismo informe durante 60 s para una combinación de periodo."""

    key = _cache_key(start_date, end_date)
    now_monotonic = monotonic()
    with _cache_lock:
        cached = _report_cache.get(key)
        if cached and cached[0] > now_monotonic:
            return cached[1]

    resolved_end = _as_utc(end_date) if end_date else datetime.now(timezone.utc)
    resolved_start = _as_utc(start_date) if start_date else resolved_end - timedelta(days=7)
    if resolved_start >= resolved_end:
        raise HTTPException(status_code=422, detail="start_date must be before end_date")

    try:
        metrics = {
            "events_per_day": events_per_day(reader, resolved_start, resolved_end),
            "error_rate_by_type": error_rate_by_type(reader, resolved_start, resolved_end),
            "latency_by_route": latency_by_route(reader, resolved_start, resolved_end),
            "auth_failure_rate": auth_failure_rate(reader, resolved_start, resolved_end),
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Telemetry report data is unavailable") from exc

    payload = {
        "period": {"from": _iso_z(resolved_start), "to": _iso_z(resolved_end)},
        "metrics": metrics,
    }
    with _cache_lock:
        _report_cache[key] = (now_monotonic + CACHE_TTL_SECONDS, payload)
    return payload
