"""MCP-only operational tool adapter for the Nexova support agent."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from agent.contracts import IncidentLookupResult


def _payload_from_tool_result(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    if isinstance(raw, list):
        for block in raw:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parsed = json.loads(block["text"])
                if isinstance(parsed, dict):
                    return parsed
    raise ValueError("MCP tool returned an unsupported result contract")


async def lookup_incident_via_mcp_async(ticket_id: int) -> IncidentLookupResult:
    """Discover and invoke the incident tool; no direct API fallback exists."""

    url = os.getenv("NEXOVA_MCP_URL", "http://nexova-mcp:8010/mcp")
    token = os.getenv("NEXOVA_MCP_ACCESS_TOKEN", "").strip()
    if not token:
        return IncidentLookupResult(ticket_id=ticket_id, found=False, error="unavailable")
    client = MultiServerMCPClient(
        {
            "nexova": {
                "transport": "http",
                "url": url,
                "headers": {"Authorization": f"Bearer {token}"},
            }
        }
    )
    try:
        tools = await client.get_tools(server_name="nexova")
        incident_tool = next(tool for tool in tools if tool.name == "get_incident_status")
        payload = _payload_from_tool_result(await incident_tool.ainvoke({"incident_id": ticket_id}))
    except (OSError, RuntimeError, StopIteration, ValueError, json.JSONDecodeError):
        return IncidentLookupResult(ticket_id=ticket_id, found=False, error="unavailable")

    if not payload.get("ok"):
        code = str((payload.get("error") or {}).get("code", ""))
        error = "not_found" if code == "NOT_FOUND" else "timeout" if code == "DOWNSTREAM_TIMEOUT" else "unavailable"
        return IncidentLookupResult(ticket_id=ticket_id, found=False, error=error)
    data = payload.get("data")
    if not isinstance(data, dict):
        return IncidentLookupResult(ticket_id=ticket_id, found=False, error="unavailable")
    try:
        return IncidentLookupResult(
            ticket_id=int(data["id"]),
            found=True,
            status=data.get("status"),
            category=data.get("category"),
            origin=data.get("origin"),
            branch=data.get("branch"),
            title=data.get("title"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
    except (KeyError, TypeError, ValueError):
        return IncidentLookupResult(ticket_id=ticket_id, found=False, error="unavailable")


def lookup_incident_via_mcp(ticket_id: int) -> IncidentLookupResult:
    """Synchronous LangGraph boundary; streaming paths use the async variant."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(lookup_incident_via_mcp_async(ticket_id))
    raise RuntimeError("Use lookup_incident_via_mcp_async inside an active event loop")


__all__ = ["lookup_incident_via_mcp", "lookup_incident_via_mcp_async"]

