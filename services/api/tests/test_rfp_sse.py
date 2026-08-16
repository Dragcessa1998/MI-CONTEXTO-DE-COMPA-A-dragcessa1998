"""Contrato HTTP/SSE y replay autenticado de notificaciones RFP."""

from __future__ import annotations

import asyncio
import json

from fastapi import Request
from fastapi.testclient import TestClient

from routes.rfp_events import rfp_event_broker
from routes.rfps import get_rfp_events


def _request() -> Request:
    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request({"type": "http", "method": "GET", "path": "/api/rfps/events", "headers": []}, receive)


def test_sse_route_requires_the_backoffice_jwt(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/api/rfps/events")

    assert response.status_code == 401


def test_sse_endpoint_frames_named_event_and_structured_context_payload() -> None:
    published = rfp_event_broker.publish({
        "ticket_id": "tkt_0341",
        "rfp_id": "rfp_0127",
        "status": "analyzing",
        "created_at": "2026-07-24T14:32:00Z",
    })

    async def inspect_response() -> tuple[object, str]:
        response = await get_rfp_events(_request(), last_event_id="0")
        chunk = await anext(response.body_iterator)
        await response.body_iterator.aclose()
        return response, chunk.decode() if isinstance(chunk, bytes) else chunk

    response, wire = asyncio.run(inspect_response())
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert f"id: {published.event_id}\n" in wire
    assert "event: rfp_ticket_created\n" in wire
    data_line = next(line for line in wire.splitlines() if line.startswith("data: "))
    assert json.loads(data_line.removeprefix("data: ")) == published.data


def test_last_event_id_replays_only_missed_tickets_without_duplicates() -> None:
    first = rfp_event_broker.publish({"ticket_id": "one", "rfp_id": "r1", "status": "analyzing"})
    second = rfp_event_broker.publish({"ticket_id": "two", "rfp_id": "r2", "status": "analyzing"})
    subscription = rfp_event_broker.subscribe(first.event_id)
    try:
        assert [event.event_id for event in subscription.replay] == [second.event_id]
        assert [event.data["ticket_id"] for event in subscription.replay] == ["two"]
    finally:
        rfp_event_broker.unsubscribe(subscription)
