"""Stable contracts shared by the LangGraph agent and its MCP adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class IncidentLookupResult(BaseModel):
    ticket_id: int
    found: bool
    status: Literal["open", "in_progress", "resolved", "discarded"] | None = None
    category: str | None = None
    origin: str | None = None
    branch: str | None = None
    title: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    error: Literal["not_found", "timeout", "unavailable"] | None = None


__all__ = ["IncidentLookupResult"]

