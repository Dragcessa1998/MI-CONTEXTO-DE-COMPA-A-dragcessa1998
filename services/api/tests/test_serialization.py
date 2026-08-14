"""Contract tests for the backend serialization audit."""

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from main import app


EXPECTED_ENDPOINTS = {
    ("GET", "/health"),
    ("POST", "/auth/login"),
    ("POST", "/auth/token"),
    ("GET", "/auth/me"),
    ("POST", "/users"),
    ("GET", "/users"),
    ("GET", "/users/{user_id}"),
    ("PUT", "/users/{user_id}"),
    ("DELETE", "/users/{user_id}"),
    ("GET", "/profiles/me"),
    ("PUT", "/profiles/me"),
    ("POST", "/suppliers"),
    ("GET", "/suppliers"),
    ("GET", "/suppliers/{supplier_id}"),
    ("PATCH", "/suppliers/{supplier_id}/rate"),
    ("PATCH", "/suppliers/{supplier_id}/status"),
    ("DELETE", "/suppliers/{supplier_id}"),
    ("POST", "/api/incidents"),
    ("GET", "/api/incidents"),
    ("GET", "/api/incidents/summary"),
    ("GET", "/api/incidents/{incident_id}"),
    ("PATCH", "/api/incidents/{incident_id}/status"),
}


def application_routes() -> list[APIRoute]:
    return [route for route in app.routes if isinstance(route, APIRoute)]


def test_audit_covers_the_complete_fastapi_surface() -> None:
    actual = {
        (method, route.path)
        for route in application_routes()
        for method in route.methods
    }

    assert actual == EXPECTED_ENDPOINTS


def test_every_non_empty_response_has_an_explicit_schema() -> None:
    missing = [
        f"{','.join(sorted(route.methods))} {route.path}"
        for route in application_routes()
        if route.status_code != 204 and route.response_model is None
    ]
    no_content = [
        route
        for route in application_routes()
        if route.path == "/users/{user_id}" and "DELETE" in route.methods
    ]

    assert missing == []
    assert len(no_content) == 1
    assert no_content[0].status_code == 204
    assert no_content[0].response_model is None


def test_registration_login_and_health_match_their_public_contracts(
    anonymous_client: TestClient,
) -> None:
    email = "serialization@nexova.example"
    registration = anonymous_client.post(
        "/users",
        json={
            "email": email,
            "password": "Serialization-2026!",
            "name": "Serialization Reviewer",
            "phone": "+34 600 000 055",
            "address": "Madrid",
        },
    )
    login = anonymous_client.post(
        "/auth/login",
        json={"email": email, "password": "Serialization-2026!"},
    )
    health = anonymous_client.get("/health")

    assert registration.status_code == 201
    assert set(registration.json()) == {"id", "is_active", "role", "created_at", "profile"}
    assert set(registration.json()["profile"]) == {"id", "name", "phone", "address"}
    assert "email" not in registration.text
    assert "password" not in registration.text

    assert login.status_code == 200
    assert set(login.json()) == {"access_token", "token_type", "expires_in"}
    assert email not in login.text

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "suppliers": 0}
