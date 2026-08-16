"""Broker SSE en memoria con replay corto para los tickets RFP de Nexova."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Any, AsyncIterator

from fastapi import Request


@dataclass(frozen=True, slots=True)
class RfpSseEvent:
    event_id: int
    data: dict[str, Any]

    def encode(self) -> str:
        payload = json.dumps(self.data, ensure_ascii=False, separators=(",", ":"))
        return f"id: {self.event_id}\nevent: rfp_ticket_created\ndata: {payload}\n\n"


@dataclass(slots=True)
class RfpEventSubscription:
    queue: asyncio.Queue[RfpSseEvent]
    replay: list[RfpSseEvent]


class RfpEventBroker:
    """Fan-out por conexión y replay acotado mediante ``Last-Event-ID``."""

    def __init__(self, replay_size: int = 100) -> None:
        self._events: deque[RfpSseEvent] = deque(maxlen=replay_size)
        self._subscribers: set[asyncio.Queue[RfpSseEvent]] = set()
        self._next_id = 1
        self._lock = Lock()

    def publish(self, data: dict[str, Any]) -> RfpSseEvent:
        with self._lock:
            event = RfpSseEvent(self._next_id, dict(data))
            self._next_id += 1
            self._events.append(event)
            subscribers = tuple(self._subscribers)
        for queue in subscribers:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)
        return event

    def subscribe(self, last_event_id: int) -> RfpEventSubscription:
        queue: asyncio.Queue[RfpSseEvent] = asyncio.Queue(maxsize=100)
        with self._lock:
            replay = [event for event in self._events if event.event_id > last_event_id]
            self._subscribers.add(queue)
        return RfpEventSubscription(queue=queue, replay=replay)

    def unsubscribe(self, subscription: RfpEventSubscription) -> None:
        with self._lock:
            self._subscribers.discard(subscription.queue)

    def reset(self) -> None:
        """Aísla pruebas sin exponer estado de producción por HTTP."""
        with self._lock:
            self._events.clear()
            self._subscribers.clear()
            self._next_id = 1


rfp_event_broker = RfpEventBroker()


async def stream_rfp_events(
    request: Request,
    last_event_id: int = 0,
    *,
    keepalive_seconds: float = 15.0,
) -> AsyncIterator[str]:
    subscription = rfp_event_broker.subscribe(last_event_id)
    try:
        for event in subscription.replay:
            yield event.encode()
        while not await request.is_disconnected():
            try:
                event = await asyncio.wait_for(
                    subscription.queue.get(),
                    timeout=keepalive_seconds,
                )
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield event.encode()
    finally:
        rfp_event_broker.unsubscribe(subscription)
