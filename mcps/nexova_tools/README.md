# Nexova Company Tools MCP Server

OAuth-protected Streamable HTTP MCP server for Nexova's first-line support
agent and future remote clients. It exposes the existing Incidents Manager and
the earlier inventory API; it does not duplicate either service's storage.

## Transport and authentication

Streamable HTTP is used because MCP Playground, Codespaces and other teams are
remote clients. Unlike stdio, the HTTP boundary needs authentication. The
server runs as an OAuth resource server using **MCP Auth** (`mcpauth`), publishes
Protected Resource Metadata, discovers a compliant OIDC provider, validates
bearer JWTs and requires `mcp:access` before discovery or invocation. FastMCP's
built-in auth helpers are not used.

Scopes are deliberately separated:

| Scope | Capability |
|---|---|
| `mcp:access` | connect and discover tools |
| `incidents:read` | check one ticket |
| `incidents:write` | create a ticket or move its lifecycle status |
| `inventory:read` | list/read stock only |

The MCP server authenticates to the internal APIs using the server-side
`NEXOVA_SERVICE_TOKEN`. It never forwards the caller's OAuth token and never
logs either token.

## Discoverable tools

| Tool | Input | Output / restriction |
|---|---|---|
| `get_incident_status` | positive `incident_id` | ID, title, category, status, origin, branch and timestamps |
| `create_incident_ticket` | title, description, exact Nexova category/origin/branch enums | creates `status=open` |
| `update_incident_status` | positive ID + exact lifecycle status | calls only `PATCH /api/incidents/{id}/status` |
| `inventory_access` | operation + optional product ID | reads `/inventory/products`; all create/update/delete attempts return `INVENTORY_READ_ONLY` without calling the backend |

FastMCP derives JSON Schemas from the function types and fields. Names,
descriptions, scope requirements and read-only behavior are visible from
`tools/list` without reading the source.

## Errors

| Layer | Code / status |
|---|---|
| Missing/malformed/invalid bearer token | OAuth `401` (`missing_auth_header`, `invalid_token`, etc.) |
| Valid token without a tool scope | OAuth `missing_required_scopes` / tool error |
| Invalid tool fields | MCP validation error / `VALIDATION_INVALID_INPUT` |
| Missing operational record | `NOT_FOUND` |
| Timeout or unavailable service | `DOWNSTREAM_TIMEOUT` / `DOWNSTREAM_UNAVAILABLE` |
| Any inventory modification | `INVENTORY_READ_ONLY` |

Every invocation logs `client`, `tool` and safe `result`; payloads, PII and
credentials are excluded.

## Run

Installations are lockfile-managed with `uv add`; no direct `pip install` is
needed.

```bash
cp mcps/nexova_tools/.env.example .env
set -a; source .env; set +a
services/api/.venv/bin/python -m mcps.nexova_tools.server
```

For MCP Playground, start this command in GitHub Codespaces, forward port 8010
with **public** visibility, set `MCP_RESOURCE_ID` and `MCP_AUTH_AUDIENCE` to that
forwarded `/mcp` URL, and connect Playground with an access token containing the
required scopes. Exercise create → status update → status check, list/get
inventory, and a write attempt. Localhost cannot be reached by the hosted
Playground.

## Agent migration

`services/api/agent/mcp_client.py` uses `MultiServerMCPClient` from
`langchain-mcp-adapters`, discovers `get_incident_status`, and invokes it over
HTTP with OAuth. Both the synchronous LangGraph node and WebSocket streaming
path call this adapter. The old direct `agent/tools.py` implementation was
removed, so there is no alternate Incidents Manager path. RAG routing remains
unchanged.

## Verification

```bash
services/api/.venv/bin/python -m pytest \
  services/api/tests/test_mcp_server.py \
  services/api/tests/test_agent_mcp_client.py \
  tests/pipelines/test_external_tools.py -q
```

The deterministic suite verifies discovery schemas, resource metadata,
unauthenticated rejection, scope rejection, the complete incident lifecycle,
explicit inventory write denial with zero backend calls, audit logs and the
agent's MCP-only route. The final hosted Playground evidence still requires a
real OIDC issuer and a public Codespaces forwarded URL.
