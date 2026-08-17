"""Contrato de validación parcial y bulk insert de telemetría."""

import json
import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient

from routes import telemetry as telemetry_route


class FakeStorage:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, Any]]] = []

    def bulk_insert(self, rows: list[dict[str, Any]]) -> None:
        self.calls.append(rows)


class FailingStorage:
    def bulk_insert(self, _rows: list[dict[str, Any]]) -> None:
        raise RuntimeError("simulated storage outage")


@pytest.fixture
def fake_storage(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    store = FakeStorage()
    monkeypatch.setattr(telemetry_route, "storage", store)
    return store


def event(event_type: str = "section_viewed") -> dict:
    return {
        "eventId": "f5bb27e4-b288-4514-8e40-fae25ff94d49",
        "timestamp": "2026-08-14T10:30:00.000Z",
        "sessionId": "session-opaque-1",
        "userId": "42",
        "event_type": event_type,
        "schemaVersion": "1.0.0",
        "requestId": "request-opaque-1",
        "properties": {
            "section": "dashboard",
            "previous_section": "login",
            "office": "unknown",
            "actor_role": "operator",
        },
    }


def test_bulk_inserts_valid_events_once_and_returns_counts(
    anonymous_client: TestClient,
    fake_storage: FakeStorage,
    caplog: pytest.LogCaptureFixture,
):
    caplog.set_level(logging.INFO, logger="routes.telemetry")
    second = event("frontend_error_captured")
    second["eventId"] = "145d9a73-fac2-46ca-a391-f94102428810"

    response = anonymous_client.post(
        "/telemetry/events",
        json={"events": [event(), second]},
    )

    assert response.status_code == 200
    assert response.json() == {"received": 2, "stored": 2, "rejected": 0}
    assert len(fake_storage.calls) == 1
    assert len(fake_storage.calls[0]) == 2
    assert "count=2 stored=2 rejected=0" in caplog.text


def test_mixed_batch_stores_valid_and_rejects_invalid_individually(
    anonymous_client: TestClient,
    fake_storage: FakeStorage,
):
    invalid = event()
    invalid.pop("requestId")

    response = anonymous_client.post(
        "/telemetry/events",
        json={"events": [event(), invalid, "not-an-object"]},
    )

    assert response.status_code == 200
    assert response.json() == {"received": 3, "stored": 1, "rejected": 2}
    assert len(fake_storage.calls) == 1
    assert len(fake_storage.calls[0]) == 1


def test_row_mapping_preserves_contract_and_allowlisted_tags(
    anonymous_client: TestClient,
    fake_storage: FakeStorage,
):
    response = anonymous_client.post("/telemetry/events", json={"events": [event()]})

    assert response.status_code == 200
    row = fake_storage.calls[0][0]
    assert set(row) == {"id", "timestamp", "service", "event_type", "level", "value", "message", "tags"}
    assert row["id"] == "f5bb27e4-b288-4514-8e40-fae25ff94d49"
    assert row["timestamp"] == "2026-08-14T10:30:00Z"
    assert row["event_type"] == "section_viewed"
    assert row["tags"] == event()["properties"]


def test_parseable_empty_batch_is_accepted_without_insert(
    anonymous_client: TestClient,
    fake_storage: FakeStorage,
):
    response = anonymous_client.post("/telemetry/events", json={"events": []})

    assert response.status_code == 200
    assert response.json() == {"received": 0, "stored": 0, "rejected": 0}
    assert fake_storage.calls == []


def test_rejects_an_unparseable_envelope(anonymous_client: TestClient):
    response = anonymous_client.post("/telemetry/events", json={"events": "invalid"})

    assert response.status_code == 422


def test_reports_storage_outage_without_leaking_details(
    anonymous_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(telemetry_route, "storage", FailingStorage())

    response = anonymous_client.post("/telemetry/events", json={"events": [event()]})

    assert response.status_code == 503
    assert response.json() == {"detail": "Telemetry storage is unavailable"}
    assert "simulated" not in response.text


def test_supabase_adapter_posts_the_whole_batch_once(
    monkeypatch: pytest.MonkeyPatch,
):
    requests: list[tuple[Any, int]] = []

    class SuccessfulResponse:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(request, timeout: int):
        requests.append((request, timeout))
        return SuccessfulResponse()

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co/")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-only-test-key")
    monkeypatch.setattr(telemetry_route, "urlopen", fake_urlopen)
    rows = [telemetry_route.event_to_row(telemetry_route.TelemetryEvent.model_validate(event()))]

    telemetry_route.SupabaseTelemetryStore().bulk_insert(rows)

    assert len(requests) == 1
    request, timeout = requests[0]
    assert request.full_url == "https://example.supabase.co/rest/v1/telemetry_events"
    assert request.method == "POST"
    assert timeout == 10
    assert json.loads(request.data) == rows
