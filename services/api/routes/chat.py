"""WebSocket autenticado del agente de soporte de primera línea."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.chat import ChatSession, chat_hub
from security import get_user_from_token


router = APIRouter(tags=["agent-chat"])
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,79}$")


class UserMessageData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    text: str = Field(min_length=1, max_length=500)


class InterruptData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    new_input: str = Field(min_length=1, max_length=500)


async def _send_events(websocket: WebSocket, queue: asyncio.Queue[dict[str, Any]]) -> None:
    while True:
        await websocket.send_json(await queue.get())


async def _handle_frame(websocket: WebSocket, session: ChatSession, frame: dict[str, Any]) -> None:
    event = frame.get("event")
    try:
        if event == "user_message":
            payload = UserMessageData.model_validate(frame.get("data"))
            if payload.session_id != session.session_id:
                raise ValueError("session_id no coincide con el socket")
            await chat_hub.user_message(session, payload.text)
            return
        if event == "interrupt_requested":
            payload = InterruptData.model_validate(frame.get("data"))
            if payload.session_id != session.session_id:
                raise ValueError("session_id no coincide con el socket")
            await chat_hub.interrupt(session, payload.new_input)
            return
        raise ValueError("Evento WebSocket no soportado")
    except (ValidationError, ValueError, RuntimeError) as exc:
        await websocket.send_json({
            "event": "error",
            "data": {"session_id": session.session_id, "detail": str(exc)},
        })


@router.websocket("/agent/ws/{session_id}")
async def support_chat_socket(
    websocket: WebSocket,
    session_id: str,
    token: str | None = None,
    client_id: str | None = None,
) -> None:
    if token is None:
        await websocket.close(code=4401, reason="JWT obligatorio")
        return
    try:
        user = get_user_from_token(token)
    except Exception:
        await websocket.close(code=4401, reason="JWT no válido")
        return
    if client_id is None or not _IDENTIFIER.fullmatch(client_id) or not _IDENTIFIER.fullmatch(session_id):
        await websocket.close(code=4400, reason="session_id/client_id no válidos")
        return
    try:
        session = chat_hub.open_session(session_id, user.id, client_id)
    except PermissionError:
        await websocket.close(code=4403, reason="Sesión de otro cliente")
        return

    queue = chat_hub.subscribe(session)
    await websocket.accept()
    await websocket.send_json({"event": "session_snapshot", "data": session.snapshot()})
    sender = asyncio.create_task(_send_events(websocket, queue), name=f"chat-sender:{session_id}")
    try:
        while True:
            frame = await websocket.receive_json()
            if not isinstance(frame, dict):
                await websocket.send_json({
                    "event": "error",
                    "data": {"session_id": session_id, "detail": "El frame debe ser un objeto JSON"},
                })
                continue
            await _handle_frame(websocket, session, frame)
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        try:
            await sender
        except (asyncio.CancelledError, WebSocketDisconnect):
            pass
        chat_hub.unsubscribe(session, queue)
