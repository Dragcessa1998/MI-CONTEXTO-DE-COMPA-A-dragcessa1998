from __future__ import annotations

import asyncio

from agent import mcp_client


class _FakeTool:
    name = "get_incident_status"

    async def ainvoke(self, payload):
        assert payload == {"incident_id": 9}
        return {
            "ok": True,
            "data": {
                "id": 9,
                "status": "open",
                "category": "technical_failure",
                "origin": "internal",
                "branch": "central",
                "title": "Error de integración",
                "created_at": "2026-08-12T08:00:00Z",
                "updated_at": "2026-08-12T08:05:00Z",
            },
        }


class _FakeClient:
    def __init__(self, config):
        assert config["nexova"]["transport"] == "http"
        assert config["nexova"]["headers"]["Authorization"] == "Bearer test-mcp-token"

    async def get_tools(self, server_name):
        assert server_name == "nexova"
        return [_FakeTool()]


def test_agent_discovers_and_calls_incident_only_through_mcp(monkeypatch) -> None:
    monkeypatch.setenv("NEXOVA_MCP_ACCESS_TOKEN", "test-mcp-token")
    monkeypatch.setattr(mcp_client, "MultiServerMCPClient", _FakeClient)

    result = asyncio.run(mcp_client.lookup_incident_via_mcp_async(9))

    assert result.found is True
    assert result.ticket_id == 9
    assert result.status == "open"


def test_agent_has_no_unauthenticated_direct_fallback(monkeypatch) -> None:
    monkeypatch.delenv("NEXOVA_MCP_ACCESS_TOKEN", raising=False)
    result = asyncio.run(mcp_client.lookup_incident_via_mcp_async(404))
    assert result.found is False and result.error == "unavailable"
