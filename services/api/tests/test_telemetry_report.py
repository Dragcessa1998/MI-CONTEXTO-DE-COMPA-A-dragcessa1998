"""Métricas Pandas, consulta acotada y caché del informe técnico."""

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from telemetry import analysis

from routes import telemetry_report as report_route


START = datetime(2026, 8, 7, tzinfo=timezone.utc)
END = datetime(2026, 8, 15, tzinfo=timezone.utc)


class FakeReader:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[datetime, datetime, tuple[str, ...] | None]] = []

    def load(self, start_date, end_date, event_types=None):
        self.calls.append((start_date, end_date, event_types))
        if event_types:
            return [row for row in self.rows if row["event_type"] in event_types]
        return self.rows


def row(
    identifier: str,
    timestamp: str,
    event_type: str,
    *,
    level: str = "info",
    value: float | None = None,
    tags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "timestamp": timestamp,
        "service": "backoffice",
        "event_type": event_type,
        "level": level,
        "value": value,
        "message": event_type.replace("_", " "),
        "tags": tags or {},
    }


def telemetry_rows() -> list[dict[str, Any]]:
    return [
        row("1", "2026-08-10T08:00:00Z", "section_viewed"),
        row("2", "2026-08-10T09:00:00Z", "frontend_error_captured", level="error"),
        row(
            "3",
            "2026-08-10T10:00:00Z",
            "api_latency_recorded",
            value=120,
            tags={"route_template": "/api/incidents", "duration_ms": 120},
        ),
        row(
            "4",
            "2026-08-11T10:00:00Z",
            "api_latency_recorded",
            value=80,
            tags={"route_template": "/api/incidents", "duration_ms": 80},
        ),
        row("5", "2026-08-11T11:00:00Z", "login_succeeded"),
        row("6", "2026-08-11T12:00:00Z", "login_failed", level="warn"),
    ]


def test_metric_functions_are_dimensioned_deterministic_and_json_safe():
    reader = FakeReader(telemetry_rows())

    first = {
        "events": analysis.events_per_day(reader, START, END),
        "errors": analysis.error_rate_by_type(reader, START, END),
        "latency": analysis.latency_by_route(reader, START, END),
        "auth": analysis.auth_failure_rate(reader, START, END),
    }
    second = {
        "events": analysis.events_per_day(reader, START, END),
        "errors": analysis.error_rate_by_type(reader, START, END),
        "latency": analysis.latency_by_route(reader, START, END),
        "auth": analysis.auth_failure_rate(reader, START, END),
    }

    assert first == second
    assert first["events"] == [
        {"date": "2026-08-10", "event_count": 3},
        {"date": "2026-08-11", "event_count": 3},
    ]
    assert first["latency"] == [
        {"route_template": "/api/incidents", "mean_latency_ms": 100.0, "sample_count": 2}
    ]
    assert first["auth"] == [
        {"date": "2026-08-11", "login_attempts": 2, "login_failures": 1, "failure_rate": 0.5}
    ]
    assert any(item["event_type"] == "frontend_error_captured" for item in first["errors"])
    json.dumps(first)


def test_supabase_reader_pushes_period_and_event_types_into_one_query(
    monkeypatch: pytest.MonkeyPatch,
):
    requests: list[Any] = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"[]"

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return Response()

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-only-test-key")
    monkeypatch.setattr(analysis, "urlopen", fake_urlopen)

    result = analysis.SupabaseTelemetryReader().load(
        START,
        END,
        ("login_failed", "login_succeeded"),
    )

    assert result == []
    assert len(requests) == 1
    request, timeout = requests[0]
    query = parse_qs(urlparse(request.full_url).query)
    assert query["timestamp"] == [f"gte.{START.isoformat()}", f"lt.{END.isoformat()}"]
    assert query["event_type"] == ["in.(login_failed,login_succeeded)"]
    assert timeout == 10


def test_report_endpoint_uses_one_period_and_the_60_second_cache(
    anonymous_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    report_route._report_cache.clear()
    calls: dict[str, int] = {"events": 0, "errors": 0, "latency": 0, "auth": 0}

    def metric(name: str):
        def calculate(_reader, start_date, end_date):
            calls[name] += 1
            assert start_date == START
            assert end_date == END
            return [{"dimension": name, "value": 1}]

        return calculate

    monkeypatch.setattr(report_route, "events_per_day", metric("events"))
    monkeypatch.setattr(report_route, "error_rate_by_type", metric("errors"))
    monkeypatch.setattr(report_route, "latency_by_route", metric("latency"))
    monkeypatch.setattr(report_route, "auth_failure_rate", metric("auth"))
    query = "?start_date=2026-08-07T00:00:00Z&end_date=2026-08-15T00:00:00Z"

    first = anonymous_client.get(f"/telemetry/report{query}")
    second = anonymous_client.get(f"/telemetry/report{query}")

    assert first.status_code == 200
    assert second.json() == first.json()
    assert first.json()["period"] == {
        "from": "2026-08-07T00:00:00Z",
        "to": "2026-08-15T00:00:00Z",
    }
    assert set(first.json()["metrics"]) == {
        "events_per_day",
        "error_rate_by_type",
        "latency_by_route",
        "auth_failure_rate",
    }
    assert calls == {"events": 1, "errors": 1, "latency": 1, "auth": 1}


def test_report_endpoint_rejects_an_inverted_period(anonymous_client: TestClient):
    report_route._report_cache.clear()
    response = anonymous_client.get(
        "/telemetry/report?start_date=2026-08-15T00:00:00Z&end_date=2026-08-07T00:00:00Z"
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "start_date must be before end_date"}
