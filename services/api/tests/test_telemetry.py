"""Contrato del stub de ingestión de telemetría."""

import logging

from fastapi.testclient import TestClient


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


def test_collects_a_batch_and_returns_received_count(
    anonymous_client: TestClient,
    caplog,
):
    caplog.set_level(logging.INFO, logger="routes.telemetry")
    response = anonymous_client.post(
        "/telemetry/events",
        json={"events": [event(), event("frontend_error_captured")]},
    )

    assert response.status_code == 200
    assert response.json() == {"received": 2}
    assert "count=2" in caplog.text
    assert "section_viewed,frontend_error_captured" in caplog.text


def test_rejects_an_invalid_envelope(anonymous_client: TestClient):
    invalid = event()
    invalid.pop("requestId")

    response = anonymous_client.post("/telemetry/events", json={"events": [invalid]})

    assert response.status_code == 422


def test_rejects_an_empty_batch(anonymous_client: TestClient):
    response = anonymous_client.post("/telemetry/events", json={"events": []})

    assert response.status_code == 422
