from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from mcp.server.fastmcp.exceptions import ToolError
from mcpauth.config import AuthServerConfig, AuthServerType, AuthorizationServerMetadata
from mcpauth.exceptions import (
    MCPAuthTokenVerificationException,
    MCPAuthTokenVerificationExceptionCode,
)
from mcpauth.types import AuthInfo

from mcps.nexova_tools.backend import BackendError
from mcps.nexova_tools.server import MCP_SCOPES, create_server


RESOURCE = "http://testserver/mcp"
ISSUER = "https://identity.nexova.test"


def _auth_server() -> AuthServerConfig:
    return AuthServerConfig(
        type=AuthServerType.OIDC,
        metadata=AuthorizationServerMetadata(
            issuer=ISSUER,
            authorization_endpoint=f"{ISSUER}/authorize",
            token_endpoint=f"{ISSUER}/token",
            jwks_uri=f"{ISSUER}/jwks",
            response_types_supported=["code"],
            scopes_supported=MCP_SCOPES,
        ),
    )


def _auth_info(scopes: list[str] | None = None) -> AuthInfo:
    return AuthInfo(
        token="valid-token",
        issuer=ISSUER,
        client_id="mcp-playground-test",
        scopes=scopes or MCP_SCOPES,
        subject="operator-7",
        audience=RESOURCE,
        claims={"sub": "operator-7"},
    )


def _verify(token: str) -> AuthInfo:
    if token != "valid-token":
        raise MCPAuthTokenVerificationException(
            MCPAuthTokenVerificationExceptionCode.INVALID_TOKEN
        )
    return _auth_info()


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def get_incident(self, incident_id: int) -> dict[str, Any]:
        self.calls.append(("get", incident_id))
        if incident_id == 404:
            raise BackendError("NOT_FOUND", "The requested record was not found.", 404)
        return {
            "id": incident_id,
            "title": "SLA superado",
            "description": "private detail excluded from MCP output",
            "category": "sla_breach",
            "status": "open",
            "origin": "customer",
            "branch": "miami_office",
            "created_at": "2026-08-17T10:00:00Z",
            "updated_at": "2026-08-17T10:00:00Z",
        }

    def create_incident(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("create", payload))
        return {"id": 41, **payload, "created_at": "2026-08-17T10:00:00Z", "updated_at": "2026-08-17T10:00:00Z"}

    def update_incident_status(self, incident_id: int, status: str) -> dict[str, Any]:
        self.calls.append(("status", incident_id, status))
        return {**self.get_incident(incident_id), "status": status}

    def list_inventory(self) -> list[dict[str, Any]]:
        self.calls.append(("inventory-list",))
        return [{"id": 3, "name": "Training laptop", "sku": "HW-003", "category": "hardware", "office": "Valencia", "current_stock": 12}]

    def get_inventory_product(self, product_id: int) -> dict[str, Any]:
        self.calls.append(("inventory-get", product_id))
        return {"id": product_id, "name": "Training laptop", "sku": "HW-003", "category": "hardware", "office": "Valencia", "current_stock": 12}


def _bundle():
    backend = FakeBackend()
    bundle = create_server(
        auth_server_config=_auth_server(),
        verify_access_token=_verify,
        backend=backend,
        resource_id=RESOURCE,
    )
    return bundle, backend


def _tool_payload(result: Any) -> dict[str, Any]:
    if isinstance(result, tuple) and len(result) == 2:
        content, structured = result
        if isinstance(structured, dict):
            return structured
        return json.loads(content[0].text)
    if getattr(result, "structuredContent", None):
        return result.structuredContent
    text = result.content[0].text
    return json.loads(text)


def test_mcp_rejects_unauthenticated_discovery_and_publishes_metadata(monkeypatch) -> None:
    monkeypatch.setenv("MCP_AUTH_AUDIENCE", RESOURCE)
    bundle, _backend = _bundle()
    with TestClient(bundle.app) as client:
        unauthorized = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={"Accept": "application/json, text/event-stream"},
        )
        metadata = client.get("/.well-known/oauth-protected-resource/mcp")

    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"] == "missing_auth_header"
    assert "resource_metadata" in unauthorized.headers["www-authenticate"]
    assert metadata.status_code == 200
    assert metadata.json()["resource"] == RESOURCE
    assert metadata.json()["scopes_supported"] == MCP_SCOPES


def test_tool_discovery_has_clear_names_descriptions_and_schemas() -> None:
    bundle, _backend = _bundle()
    tools = asyncio.run(bundle.mcp.list_tools())
    discovered = {tool.name: tool for tool in tools}

    assert set(discovered) == {
        "get_incident_status",
        "create_incident_ticket",
        "update_incident_status",
        "inventory_access",
    }
    assert "incidents:read" in discovered["get_incident_status"].description
    assert discovered["create_incident_ticket"].inputSchema["properties"]["category"]["enum"]
    assert "INVENTORY_READ_ONLY" in discovered["inventory_access"].description


def test_incident_flow_uses_lifecycle_backend_and_filters_description() -> None:
    bundle, backend = _bundle()
    token = bundle.auth._context_var.set(_auth_info())
    try:
        created = asyncio.run(
            bundle.mcp.call_tool(
                "create_incident_ticket",
                {
                    "title": "Demora de soporte",
                    "description": "El cliente superó el SLA esperado.",
                    "category": "sla_breach",
                    "origin": "customer",
                    "branch": "miami_office",
                },
            )
        )
        updated = asyncio.run(
            bundle.mcp.call_tool(
                "update_incident_status",
                {"incident_id": 41, "status": "in_progress"},
            )
        )
        checked = asyncio.run(
            bundle.mcp.call_tool("get_incident_status", {"incident_id": 41})
        )
    finally:
        bundle.auth._context_var.reset(token)

    assert _tool_payload(created)["data"]["id"] == 41
    assert _tool_payload(updated)["data"]["status"] == "in_progress"
    assert "description" not in _tool_payload(checked)["data"]
    assert ("status", 41, "in_progress") in backend.calls


def test_inventory_write_is_explicitly_rejected_without_backend_mutation(caplog) -> None:
    bundle, backend = _bundle()
    token = bundle.auth._context_var.set(_auth_info())
    try:
        result = asyncio.run(
            bundle.mcp.call_tool(
                "inventory_access",
                {"operation": "delete_product", "product_id": 3},
            )
        )
    finally:
        bundle.auth._context_var.reset(token)

    payload = _tool_payload(result)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVENTORY_READ_ONLY"
    assert backend.calls == []
    assert "INVENTORY_READ_ONLY" in caplog.text


def test_missing_tool_scope_is_distinct_from_authentication_failure() -> None:
    bundle, _backend = _bundle()
    token = bundle.auth._context_var.set(_auth_info(["mcp:access", "incidents:read"]))
    try:
        with pytest.raises(ToolError, match="necessary scopes"):
            asyncio.run(
                bundle.mcp.call_tool(
                    "create_incident_ticket",
                    {
                        "title": "Demora de soporte",
                        "description": "El cliente superó el SLA esperado.",
                        "category": "sla_breach",
                        "origin": "customer",
                        "branch": "miami_office",
                    },
                )
            )
    finally:
        bundle.auth._context_var.reset(token)
