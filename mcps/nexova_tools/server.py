"""OAuth 2.1/OIDC protected Streamable HTTP MCP server for Nexova."""

from __future__ import annotations

import contextlib
import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Literal, Protocol

from mcp.server.fastmcp import FastMCP
from mcpauth import MCPAuth
from mcpauth.config import AuthServerConfig, AuthServerType
from mcpauth.exceptions import BearerAuthExceptionCode, MCPAuthBearerAuthException
from mcpauth.types import AuthInfo, ResourceServerConfig, ResourceServerMetadata, VerifyAccessTokenFunction
from mcpauth.utils import fetch_server_config
from pydantic import Field
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import Mount

from .backend import BackendError, NexovaBackendClient


logger = logging.getLogger("nexova.mcp.tools")
MCP_SCOPES = ["mcp:access", "incidents:read", "incidents:write", "inventory:read"]
IncidentCategory = Literal[
    "technical_failure",
    "process_error",
    "client_complaint",
    "candidate_issue",
    "staff_issue",
    "sla_breach",
    "data_quality",
    "other",
]
IncidentOrigin = Literal["customer", "branch", "internal"]
IncidentBranch = Literal["central", "valencia_operations", "miami_office", "remote"]
IncidentStatus = Literal["open", "in_progress", "resolved", "discarded"]
InventoryOperation = Literal[
    "list_products",
    "get_product",
    "create_product",
    "update_product",
    "delete_product",
]


class OperationalBackend(Protocol):
    def get_incident(self, incident_id: int) -> dict[str, Any]: ...
    def create_incident(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def update_incident_status(self, incident_id: int, status: str) -> dict[str, Any]: ...
    def list_inventory(self) -> list[dict[str, Any]]: ...
    def get_inventory_product(self, product_id: int) -> dict[str, Any]: ...


def _public_incident(record: dict[str, Any]) -> dict[str, Any]:
    allowed = {"id", "title", "category", "status", "origin", "branch", "created_at", "updated_at"}
    return {key: value for key, value in record.items() if key in allowed}


def _public_product(record: dict[str, Any]) -> dict[str, Any]:
    allowed = {"id", "name", "sku", "category", "office", "current_stock"}
    return {key: value for key, value in record.items() if key in allowed}


class ToolRuntime:
    def __init__(self, auth: MCPAuth, backend: OperationalBackend) -> None:
        self.auth = auth
        self.backend = backend

    def _identity(self, tool: str, required_scope: str) -> AuthInfo:
        info = self.auth.auth_info
        if info is None:
            logger.warning("mcp_tool_invocation client=unknown tool=%s result=unauthenticated", tool)
            raise MCPAuthBearerAuthException(BearerAuthExceptionCode.MISSING_AUTH_HEADER)
        if required_scope not in info.scopes:
            logger.warning(
                "mcp_tool_invocation client=%s tool=%s result=insufficient_scope",
                info.client_id or info.subject,
                tool,
            )
            raise MCPAuthBearerAuthException(BearerAuthExceptionCode.MISSING_REQUIRED_SCOPES)
        return info

    def run(self, tool: str, required_scope: str, action: Callable[[], Any]) -> dict[str, Any]:
        info = self._identity(tool, required_scope)
        client = info.client_id or info.subject
        try:
            data = action()
        except BackendError as exc:
            logger.warning("mcp_tool_invocation client=%s tool=%s result=%s", client, tool, exc.code)
            return {"ok": False, "error": {"code": exc.code, "message": exc.message}}
        logger.info("mcp_tool_invocation client=%s tool=%s result=success", client, tool)
        return {"ok": True, "data": data}


@dataclass(frozen=True)
class MCPServerBundle:
    mcp: FastMCP
    app: Starlette
    auth: MCPAuth
    runtime: ToolRuntime


def create_server(
    *,
    auth_server_config: AuthServerConfig,
    verify_access_token: VerifyAccessTokenFunction | None = None,
    backend: OperationalBackend | None = None,
    resource_id: str | None = None,
) -> MCPServerBundle:
    """Build a server; injectable auth/backend keep acceptance tests deterministic."""

    resource = resource_id or os.getenv("MCP_RESOURCE_ID", "http://localhost:8010/mcp")
    mcp = FastMCP(name="Nexova Company Tools", stateless_http=True)
    auth = MCPAuth(
        protected_resources=[
            ResourceServerConfig(
                metadata=ResourceServerMetadata(
                    resource=resource,
                    resource_name="Nexova operational MCP tools",
                    resource_documentation="https://github.com/Dragcessa1998/MI-CONTEXTO-DE-COMPA-A-dragcessa1998/tree/feature/mcp-oauth-tools/mcps/nexova_tools",
                    authorization_servers=[auth_server_config],
                    scopes_supported=MCP_SCOPES,
                    bearer_methods_supported=["header"],
                )
            )
        ]
    )
    runtime = ToolRuntime(auth, backend or NexovaBackendClient())

    @mcp.tool(
        name="get_incident_status",
        description=(
            "Read one real Nexova Incidents Manager ticket by positive integer ID. "
            "Requires incidents:read. Returns only operational status fields and never credentials."
        ),
    )
    def get_incident_status(incident_id: int = Field(gt=0)) -> dict[str, Any]:
        return runtime.run(
            "get_incident_status",
            "incidents:read",
            lambda: _public_incident(runtime.backend.get_incident(incident_id)),
        )

    @mcp.tool(
        name="create_incident_ticket",
        description=(
            "Create a Nexova support incident using the exact Incidents Manager fields. "
            "Requires incidents:write. Initial status is open."
        ),
    )
    def create_incident_ticket(
        title: str = Field(min_length=1, max_length=120),
        description: str = Field(min_length=5, max_length=10_000),
        category: IncidentCategory = "other",
        origin: IncidentOrigin = "customer",
        branch: IncidentBranch = "central",
    ) -> dict[str, Any]:
        payload = {
            "title": title,
            "description": description,
            "category": category,
            "status": "open",
            "origin": origin,
            "branch": branch,
        }
        return runtime.run(
            "create_incident_ticket",
            "incidents:write",
            lambda: _public_incident(runtime.backend.create_incident(payload)),
        )

    @mcp.tool(
        name="update_incident_status",
        description=(
            "Move a real Nexova ticket through its lifecycle using PATCH "
            "/api/incidents/{id}/status. Requires incidents:write."
        ),
    )
    def update_incident_status(
        incident_id: int = Field(gt=0),
        status: IncidentStatus = "in_progress",
    ) -> dict[str, Any]:
        return runtime.run(
            "update_incident_status",
            "incidents:write",
            lambda: _public_incident(runtime.backend.update_incident_status(incident_id, status)),
        )

    @mcp.tool(
        name="inventory_access",
        description=(
            "Read Nexova inventory products using list_products or get_product. "
            "Requires inventory:read. create_product, update_product and delete_product "
            "are accepted only to return the explicit INVENTORY_READ_ONLY rejection; this MCP "
            "server can never mutate inventory."
        ),
    )
    def inventory_access(
        operation: InventoryOperation,
        product_id: int | None = Field(default=None, gt=0),
    ) -> dict[str, Any]:
        info = runtime._identity("inventory_access", "inventory:read")
        client = info.client_id or info.subject
        if operation in {"create_product", "update_product", "delete_product"}:
            logger.warning(
                "mcp_tool_invocation client=%s tool=inventory_access result=INVENTORY_READ_ONLY",
                client,
            )
            return {
                "ok": False,
                "error": {
                    "code": "INVENTORY_READ_ONLY",
                    "message": "Inventory modification is forbidden through this MCP server.",
                },
            }
        if operation == "get_product" and product_id is None:
            logger.warning(
                "mcp_tool_invocation client=%s tool=inventory_access result=VALIDATION_INVALID_INPUT",
                client,
            )
            return {
                "ok": False,
                "error": {
                    "code": "VALIDATION_INVALID_INPUT",
                    "message": "product_id is required for get_product.",
                },
            }
        action: Callable[[], Any]
        if operation == "list_products":
            action = lambda: [_public_product(item) for item in runtime.backend.list_inventory()]
        else:
            action = lambda: _public_product(runtime.backend.get_inventory_product(int(product_id)))
        return runtime.run("inventory_access", "inventory:read", action)

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette):
        async with contextlib.AsyncExitStack() as stack:
            await stack.enter_async_context(mcp.session_manager.run())
            yield

    verifier: Literal["jwt"] | VerifyAccessTokenFunction = verify_access_token or "jwt"
    bearer_auth = Middleware(
        auth.bearer_auth_middleware(
            verifier,
            audience=os.getenv("MCP_AUTH_AUDIENCE", resource),
            required_scopes=["mcp:access"],
            resource=resource,
        )
    )
    app = Starlette(
        routes=[
            *auth.resource_metadata_router().routes,
            Mount("/", app=mcp.streamable_http_app(), middleware=[bearer_auth]),
        ],
        lifespan=lifespan,
    )
    return MCPServerBundle(mcp=mcp, app=app, auth=auth, runtime=runtime)


def create_app() -> Starlette:
    """Uvicorn factory using live OIDC discovery and MCP Auth JWT validation."""

    issuer = os.getenv("MCP_AUTH_ISSUER", "").strip()
    if not issuer:
        raise RuntimeError("MCP_AUTH_ISSUER must identify a compliant OAuth 2.1/OIDC provider")
    auth_server = fetch_server_config(issuer, AuthServerType.OIDC)
    return create_server(auth_server_config=auth_server).app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "mcps.nexova_tools.server:create_app",
        factory=True,
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_PORT", "8010")),
    )


__all__ = ["MCP_SCOPES", "MCPServerBundle", "create_app", "create_server"]
