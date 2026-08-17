"""Least-privilege HTTP adapter for Nexova's existing operational APIs."""

from __future__ import annotations

import os
from typing import Any

import httpx


class BackendError(RuntimeError):
    """Safe downstream failure classified for MCP clients."""

    def __init__(self, code: str, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _error_for_status(status_code: int) -> BackendError:
    if status_code == 404:
        return BackendError("NOT_FOUND", "The requested record was not found.", 404)
    if status_code == 409:
        return BackendError("CONFLICT", "The requested operation conflicts with current state.", 409)
    if status_code in {400, 422}:
        return BackendError("VALIDATION_INVALID_INPUT", "The service rejected the supplied fields.", status_code)
    if status_code in {401, 403}:
        return BackendError("DOWNSTREAM_AUTH_FAILED", "The operational service denied access.", 502)
    return BackendError("DOWNSTREAM_UNAVAILABLE", "The operational service is unavailable.", 502)


class NexovaBackendClient:
    """Calls real incident/inventory APIs with a server-side service token."""

    def __init__(
        self,
        *,
        incidents_url: str | None = None,
        inventory_url: str | None = None,
        service_token: str | None = None,
        timeout_seconds: float = 4.0,
    ) -> None:
        self.incidents_url = (incidents_url or os.getenv("INCIDENTS_API_URL", "http://backend:8000")).rstrip("/")
        self.inventory_url = (inventory_url or os.getenv("INVENTORY_API_URL", "http://inventory-api:8000")).rstrip("/")
        self.service_token = service_token if service_token is not None else os.getenv("NEXOVA_SERVICE_TOKEN", "")
        self.timeout_seconds = timeout_seconds

    def _request(
        self,
        method: str,
        base_url: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> Any:
        headers = {"Accept": "application/json"}
        if self.service_token:
            headers["Authorization"] = f"Bearer {self.service_token}"
        try:
            response = httpx.request(
                method,
                f"{base_url}{path}",
                headers=headers,
                json=body,
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise BackendError("DOWNSTREAM_TIMEOUT", "The operational service timed out.", 504) from exc
        except httpx.HTTPError as exc:
            raise BackendError("DOWNSTREAM_UNAVAILABLE", "The operational service is unavailable.", 502) from exc
        if response.status_code >= 400:
            raise _error_for_status(response.status_code)
        try:
            return response.json()
        except ValueError as exc:
            raise BackendError("DOWNSTREAM_INVALID_RESPONSE", "The operational service returned invalid data.", 502) from exc

    def get_incident(self, incident_id: int) -> dict[str, Any]:
        return self._request("GET", self.incidents_url, f"/api/incidents/{incident_id}")

    def create_incident(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", self.incidents_url, "/api/incidents", body=payload)

    def update_incident_status(self, incident_id: int, status: str) -> dict[str, Any]:
        # The lifecycle endpoint is intentional; generic incident PATCH is forbidden.
        return self._request(
            "PATCH",
            self.incidents_url,
            f"/api/incidents/{incident_id}/status",
            body={"status": status},
        )

    def list_inventory(self) -> list[dict[str, Any]]:
        result = self._request("GET", self.inventory_url, "/inventory/products")
        if not isinstance(result, list):
            raise BackendError("DOWNSTREAM_INVALID_RESPONSE", "Inventory returned an invalid collection.", 502)
        return result

    def get_inventory_product(self, product_id: int) -> dict[str, Any]:
        return self._request("GET", self.inventory_url, f"/inventory/products/{product_id}")


__all__ = ["BackendError", "NexovaBackendClient"]

