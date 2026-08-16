"""Evidencia reproducible de remediaciones OWASP en la API acumulativa."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app_security import allowed_cors_origins


def test_api_sets_defensive_headers(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert "camera=()" in response.headers["permissions-policy"]


def test_cors_allows_known_backoffice_and_rejects_unknown_origin(
    anonymous_client: TestClient,
) -> None:
    allowed = anonymous_client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = anonymous_client.options(
        "/health",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3001"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_cors_configuration_refuses_wildcard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")

    with pytest.raises(RuntimeError, match="allowlist explícita"):
        allowed_cors_origins()


def test_support_role_cannot_open_privileged_rfp_workflow(
    anonymous_client: TestClient,
) -> None:
    registration = anonymous_client.post(
        "/users",
        json={
            "email": "support-only@nexova.example",
            "password": "SupportOnly-2026!",
            "name": "Support Operator",
        },
    )
    assert registration.status_code == 201
    login = anonymous_client.post(
        "/auth/login",
        json={"email": "support-only@nexova.example", "password": "SupportOnly-2026!"},
    )

    response = anonymous_client.get(
        "/api/rfps",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "No tienes permiso para realizar esta acción"
