"""Adaptador de streaming del agente existente, sin cambiar sus tools ni rutas."""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator

from agent.graph import (
    EMPTY_QUESTION_ANSWER,
    INCIDENT_FALLBACK,
    format_incident_answer,
    format_incident_suffix,
    select_route,
)
from agent.tools import IncidentLookupInput, lookup_incident
from data.pipelines.rag import NO_CONTEXT_ANSWER, generate_answer_stream, retrieve


_TICKET_ID = re.compile(r"\b(?:ticket|incidente|incidencia)\s*(?:#|n[úu]mero|id)?\s*(\d+)\b", re.IGNORECASE)


async def _fixed_tokens(text: str) -> AsyncIterator[str]:
    for token in re.findall(r"\S+\s*", text):
        await asyncio.sleep(0)
        yield token


async def _incident_answer(question: str) -> AsyncIterator[str]:
    match = _TICKET_ID.search(question)
    if match is None:
        async for token in _fixed_tokens("Indica el número del ticket que quieres consultar."):
            yield token
        return
    result = await asyncio.to_thread(lookup_incident, IncidentLookupInput(ticket_id=int(match.group(1))))
    answer = format_incident_answer(result.model_dump(mode="json")) if result.found else INCIDENT_FALLBACK
    async for token in _fixed_tokens(answer):
        yield token


async def stream_support_agent(question: str, _session_id: str) -> AsyncIterator[str]:
    """Misma selección RAG/tool; el tramo generativo usa deltas reales y cancelables."""

    normalized = question.strip()
    route = select_route(normalized)
    if route == "invalid":
        async for token in _fixed_tokens(EMPTY_QUESTION_ANSWER):
            yield token
        return
    if route == "tool":
        async for token in _incident_answer(normalized):
            yield token
        return

    context = await asyncio.to_thread(retrieve, normalized)
    if not context:
        if route == "both":
            async for token in _incident_answer(normalized):
                yield token
        else:
            async for token in _fixed_tokens(NO_CONTEXT_ANSWER):
                yield token
        return

    async for token in generate_answer_stream(normalized, context):
        yield token

    if route == "both":
        match = _TICKET_ID.search(normalized)
        if match is None:
            suffix = "\n\nIndica el número del ticket que quieres consultar."
        else:
            result = await asyncio.to_thread(
                lookup_incident,
                IncidentLookupInput(ticket_id=int(match.group(1))),
            )
            suffix = format_incident_suffix(result.model_dump(mode="json")) if result.found else f"\n\n{INCIDENT_FALLBACK}"
        async for token in _fixed_tokens(suffix):
            yield token


__all__ = ["stream_support_agent"]
