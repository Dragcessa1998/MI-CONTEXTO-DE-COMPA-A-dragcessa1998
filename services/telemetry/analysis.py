"""Pipeline Pandas para el informe técnico de telemetría de Nexova."""

import json
import os
from datetime import datetime
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

import pandas as pd


TELEMETRY_COLUMNS = [
    "id",
    "timestamp",
    "service",
    "event_type",
    "level",
    "value",
    "message",
    "tags",
]


class TelemetryReader(Protocol):
    """Carga acotada equivalente a un SELECT con filtros en SQL."""

    def load(
        self,
        start_date: datetime,
        end_date: datetime,
        event_types: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]: ...


class SupabaseTelemetryReader:
    """Lee sólo las filas requeridas mediante PostgREST/Supabase."""

    def load(
        self,
        start_date: datetime,
        end_date: datetime,
        event_types: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not supabase_url or not service_key:
            raise RuntimeError("Supabase telemetry storage is not configured")

        params: list[tuple[str, str]] = [
            ("select", ",".join(TELEMETRY_COLUMNS)),
            ("timestamp", f"gte.{start_date.isoformat()}"),
            ("timestamp", f"lt.{end_date.isoformat()}"),
            ("order", "timestamp.asc"),
        ]
        if event_types:
            params.append(("event_type", f"in.({','.join(event_types)})"))

        request = UrlRequest(
            f"{supabase_url}/rest/v1/telemetry_events?{urlencode(params)}",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                rows = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, json.JSONDecodeError) as exc:
            raise RuntimeError("Supabase telemetry query failed") from exc
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise RuntimeError("Supabase telemetry query returned an invalid payload")
        return rows


def _load_frame(
    reader: TelemetryReader,
    start_date: datetime,
    end_date: datetime,
    event_types: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Load (SQL push-down) → refine (fixed eight-column contract)."""

    rows = reader.load(start_date, end_date, event_types)
    return pd.DataFrame.from_records(rows).reindex(columns=TELEMETRY_COLUMNS)


def _with_utc_date(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert types before every temporal groupby."""

    converted = frame.copy()
    converted["timestamp"] = pd.to_datetime(converted["timestamp"], utc=True, errors="coerce")
    converted = converted.dropna(subset=["timestamp"]).reset_index(drop=True)
    converted["date"] = converted["timestamp"].dt.strftime("%Y-%m-%d")
    return converted


def events_per_day(
    reader: TelemetryReader,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Volumen diario: detecta caídas o picos de instrumentación."""

    frame = _with_utc_date(_load_frame(reader, start_date, end_date))
    if frame.empty:
        return []
    result = frame.groupby("date", as_index=False).agg(event_count=("id", "count"))
    return result.to_dict(orient="records")


def error_rate_by_type(
    reader: TelemetryReader,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Tasa diaria de error segmentada por tipo de evento."""

    frame = _with_utc_date(_load_frame(reader, start_date, end_date))
    if frame.empty:
        return []
    frame["is_error"] = frame["level"].eq("error") | frame["event_type"].str.contains(
        "error|failed", case=False, na=False
    )
    result = frame.groupby(["date", "event_type"], as_index=False).agg(
        total_events=("id", "count"),
        error_events=("is_error", "sum"),
    )
    result["error_rate"] = (result["error_events"] / result["total_events"]).round(4)
    return result.to_dict(orient="records")


def latency_by_route(
    reader: TelemetryReader,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Latencia media por ruta: localiza endpoints operativamente lentos."""

    frame = _load_frame(reader, start_date, end_date, ("api_latency_recorded",))
    if frame.empty:
        return []
    tags = pd.json_normalize(frame["tags"]).reindex(index=frame.index)
    frame = frame.assign(
        route_template=tags.get("route_template"),
        duration_ms=pd.to_numeric(tags.get("duration_ms", frame["value"]), errors="coerce"),
    ).dropna(subset=["route_template", "duration_ms"])
    result = frame.groupby("route_template", as_index=False).agg(
        mean_latency_ms=("duration_ms", "mean"),
        sample_count=("id", "count"),
    )
    result["mean_latency_ms"] = result["mean_latency_ms"].round(2)
    return result.to_dict(orient="records")


def auth_failure_rate(
    reader: TelemetryReader,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Fallos de login por día sobre todos los intentos de autenticación."""

    frame = _with_utc_date(
        _load_frame(reader, start_date, end_date, ("login_failed", "login_succeeded"))
    )
    if frame.empty:
        return []
    frame["is_failed"] = frame["event_type"].eq("login_failed")
    result = frame.groupby("date", as_index=False).agg(
        login_attempts=("id", "count"),
        login_failures=("is_failed", "sum"),
    )
    result["failure_rate"] = (result["login_failures"] / result["login_attempts"]).round(4)
    return result.to_dict(orient="records")
