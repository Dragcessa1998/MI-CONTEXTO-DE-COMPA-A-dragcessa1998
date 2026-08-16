"""Sesiones, historial y pub/sub del chat WebSocket de soporte."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from agent.streaming import stream_support_agent


TokenSource = Callable[[str, str], AsyncIterator[str]]


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class ChatSession:
    session_id: str
    user_id: int
    client_id: str
    agent_id: str = "first_line_support"
    status: str = "active"
    created_at: str = field(default_factory=_now)
    messages: list[dict[str, Any]] = field(default_factory=list)
    subscribers: set[asyncio.Queue[dict[str, Any]]] = field(default_factory=set)
    generation_task: asyncio.Task[None] | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "client_id": self.client_id,
            "status": self.status,
            "created_at": self.created_at,
            "messages": [dict(message) for message in self.messages],
        }


class ChatHub:
    """Un productor por sesión y cualquier número de consumidores WebSocket."""

    def __init__(self, token_source: TokenSource = stream_support_agent, max_sessions: int = 200) -> None:
        self.token_source = token_source
        self.max_sessions = max_sessions
        self._sessions: dict[str, ChatSession] = {}

    def open_session(self, session_id: str, user_id: int, client_id: str) -> ChatSession:
        current = self._sessions.get(session_id)
        if current is not None:
            if current.user_id != user_id or current.client_id != client_id:
                raise PermissionError("La sesión pertenece a otro cliente")
            return current
        if len(self._sessions) >= self.max_sessions:
            oldest = next(iter(self._sessions))
            old_session = self._sessions[oldest]
            if old_session.generation_task is None or old_session.generation_task.done():
                self._sessions.pop(oldest)
        session = ChatSession(session_id=session_id, user_id=user_id, client_id=client_id)
        self._sessions[session_id] = session
        return session

    def subscribe(self, session: ChatSession) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
        session.subscribers.add(queue)
        return queue

    def unsubscribe(self, session: ChatSession, queue: asyncio.Queue[dict[str, Any]]) -> None:
        session.subscribers.discard(queue)

    def publish(self, session: ChatSession, event: dict[str, Any]) -> None:
        for queue in tuple(session.subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)

    async def user_message(self, session: ChatSession, text: str) -> None:
        normalized = text.strip()
        if not normalized:
            raise ValueError("El mensaje no puede estar vacío")
        async with session.lock:
            if session.generation_task is not None and not session.generation_task.done():
                raise RuntimeError("Hay una generación activa; interrúmpela antes de enviar otro mensaje")
            message = {
                "message_id": f"msg_{uuid4().hex}",
                "role": "user",
                "content": normalized,
                "status": "completed",
                "created_at": _now(),
            }
            session.messages.append(message)
            session.status = "active"
            self.publish(session, {
                "event": "user_message",
                "data": {
                    "session_id": session.session_id,
                    "message_id": message["message_id"],
                    "text": normalized,
                },
            })
            session.generation_task = asyncio.create_task(
                self._generate(session, normalized),
                name=f"support-generation:{session.session_id}",
            )

    async def interrupt(self, session: ChatSession, new_input: str) -> None:
        normalized = new_input.strip()
        if not normalized:
            raise ValueError("new_input es obligatorio")
        async with session.lock:
            task = session.generation_task
        if task is None or task.done():
            raise RuntimeError("No hay una generación activa que interrumpir")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await self.user_message(session, normalized)

    async def _generate(self, session: ChatSession, text: str) -> None:
        message = {
            "message_id": f"msg_{uuid4().hex}",
            "role": "assistant",
            "content": "",
            "status": "streaming",
            "created_at": _now(),
        }
        session.messages.append(message)
        sequence = 0
        current_task = asyncio.current_task()
        try:
            async for token in self.token_source(text, session.session_id):
                sequence += 1
                message["content"] += token
                self.publish(session, {
                    "event": "token_chunk",
                    "data": {
                        "session_id": session.session_id,
                        "message_id": message["message_id"],
                        "token": token,
                        "sequence": sequence,
                    },
                })
            message["status"] = "completed"
            self.publish(session, {
                "event": "generation_completed",
                "data": {"session_id": session.session_id, "message_id": message["message_id"]},
            })
        except asyncio.CancelledError:
            message["status"] = "interrupted"
            session.status = "interrupted"
            self.publish(session, {
                "event": "generation_interrupted",
                "data": {
                    "session_id": session.session_id,
                    "message_id": message["message_id"],
                    "status": "interrupted",
                },
            })
            raise
        except Exception:
            message["status"] = "failed"
            self.publish(session, {
                "event": "generation_failed",
                "data": {
                    "session_id": session.session_id,
                    "message_id": message["message_id"],
                    "detail": "El agente no está disponible temporalmente.",
                },
            })
        finally:
            async with session.lock:
                if session.generation_task is current_task:
                    session.generation_task = None


chat_hub = ChatHub()


__all__ = ["ChatHub", "ChatSession", "chat_hub"]
