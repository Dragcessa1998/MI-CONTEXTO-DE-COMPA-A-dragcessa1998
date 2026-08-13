"""Acceptance coverage for password recovery, one-time tokens, and change flow."""

import hashlib
import json
from datetime import timedelta

from fastapi.testclient import TestClient

import database
import email_service
import routes.auth as auth_routes
from security import create_password_reset_token


PASSWORD = "SecurePassword-2026!"
NEW_PASSWORD = "NewSecurePassword-2026!"


def register(client: TestClient, email: str = "reset@nexova.example") -> dict:
    response = client.post(
        "/users",
        json={"email": email, "password": PASSWORD, "name": "Reset Test"},
    )
    assert response.status_code == 201
    return response.json()


def login(client: TestClient, email: str, password: str = PASSWORD) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def capture_reset_token(monkeypatch, client: TestClient, email: str) -> str:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        auth_routes,
        "try_send_password_reset_email",
        lambda recipient, token: sent.append((recipient, token)),
    )
    response = client.post("/auth/forgot-password", json={"email": email})
    assert response.status_code == 200
    assert sent and sent[0][0] == email
    return sent[0][1]


def test_forgot_password_never_reveals_whether_account_exists(
    anonymous_client: TestClient,
    monkeypatch,
):
    user = register(anonymous_client)
    sent: list[str] = []
    monkeypatch.setattr(
        auth_routes,
        "try_send_password_reset_email",
        lambda _recipient, token: sent.append(token),
    )

    known = anonymous_client.post("/auth/forgot-password", json={"email": user["email"]})
    unknown = anonymous_client.post(
        "/auth/forgot-password", json={"email": "unknown@nexova.example"}
    )

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert len(sent) == 1
    stored = database.password_reset_tokens_table().all()[0]
    assert "token" not in stored
    assert stored["token_hash"] == hashlib.sha256(sent[0].encode()).hexdigest()


def test_reset_password_changes_credentials_and_token_is_one_time(
    anonymous_client: TestClient,
    monkeypatch,
):
    user = register(anonymous_client)
    token = capture_reset_token(monkeypatch, anonymous_client, user["email"])

    reset = anonymous_client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": NEW_PASSWORD},
    )
    replay = anonymous_client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "AnotherSecurePassword-2026!"},
    )

    assert reset.status_code == 200
    assert replay.status_code == 400
    assert anonymous_client.post(
        "/auth/login", json={"email": user["email"], "password": PASSWORD}
    ).status_code == 401
    assert anonymous_client.post(
        "/auth/login", json={"email": user["email"], "password": NEW_PASSWORD}
    ).status_code == 200
    assert database.password_reset_tokens_table().all()[0]["used_at"] is not None


def test_reset_password_rejects_invalid_and_expired_tokens(anonymous_client: TestClient):
    user = register(anonymous_client)
    expired, _ = create_password_reset_token(
        user["id"], "expired-token-id", expires_delta=timedelta(seconds=-1)
    )

    invalid = anonymous_client.post(
        "/auth/reset-password",
        json={"token": "not-a-token", "new_password": NEW_PASSWORD},
    )
    expired_response = anonymous_client.post(
        "/auth/reset-password",
        json={"token": expired, "new_password": NEW_PASSWORD},
    )

    assert invalid.status_code == expired_response.status_code == 400


def test_change_password_requires_session_and_correct_current_password(
    anonymous_client: TestClient,
):
    user = register(anonymous_client)
    token = login(anonymous_client, user["email"])
    headers = {"Authorization": f"Bearer {token}"}

    missing = anonymous_client.post(
        "/auth/change-password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    wrong = anonymous_client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "wrong-password", "new_password": NEW_PASSWORD},
    )
    changed = anonymous_client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 400
    assert changed.status_code == 200
    assert anonymous_client.post(
        "/auth/login", json={"email": user["email"], "password": NEW_PASSWORD}
    ).status_code == 200


def test_resend_adapter_uses_environment_and_mobile_readable_html(monkeypatch):
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("RESEND_API_KEY", "re_test_secret")
    monkeypatch.setenv("PASSWORD_RESET_FROM_EMAIL", "Nexova <onboarding@resend.dev>")
    monkeypatch.setenv("PASSWORD_RESET_FRONTEND_URL", "http://localhost:3000/reset-password")
    monkeypatch.setattr(email_service, "urlopen", fake_urlopen)

    email_service.send_password_reset_email("person@example.com", "signed-token")

    request = captured["request"]
    body = json.loads(request.data)
    assert request.full_url == "https://api.resend.com/emails"
    assert request.get_header("Authorization") == "Bearer re_test_secret"
    assert body["to"] == ["person@example.com"]
    assert "reset-password?token=signed-token" in body["html"]
    assert "max-width:560px" in body["html"]
