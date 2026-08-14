"""Acceptance coverage for JWT authentication, ownership and TinyDB separation."""

from datetime import timedelta

from fastapi.testclient import TestClient
from tinydb import Query

import database
from security import create_access_token, verify_password


def user_payload(email: str = "maria@nexova.example", **overrides) -> dict:
    payload = {
        "email": email,
        "password": "SecurePassword-2026!",
        "name": "María López",
        "phone": "+34 600 000 001",
        "address": "Valencia",
    }
    payload.update(overrides)
    return payload


def register(client: TestClient, email: str = "maria@nexova.example", **overrides) -> dict:
    response = client.post("/users", json=user_payload(email, **overrides))
    assert response.status_code == 201
    body = response.json()
    assert "email" not in body
    body["_email"] = email.strip().lower()
    return body


def login(client: TestClient, email: str, password: str = "SecurePassword-2026!") -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["expires_in"] == 1800
    return response.json()["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_registration_hashes_password_and_creates_separate_profile(
    anonymous_client: TestClient,
):
    body = register(anonymous_client)

    assert body["role"] == "user"
    assert body["is_active"] is True
    assert body["profile"] == {
        "id": 1,
        "name": "María López",
        "phone": "+34 600 000 001",
        "address": "Valencia",
    }
    stored_user = database.users_table().get(Query().id == body["id"])
    stored_profile = database.profiles_table().get(Query().user_id == body["id"])
    assert stored_user["hashed_password"] != "SecurePassword-2026!"
    assert verify_password("SecurePassword-2026!", stored_user["hashed_password"])
    assert not {"name", "phone", "address"}.intersection(stored_user)
    assert "hashed_password" not in body
    assert "password" not in body
    assert stored_profile["name"] == "María López"


def test_registration_normalizes_email_and_rejects_duplicates(
    anonymous_client: TestClient,
):
    first = anonymous_client.post("/users", json=user_payload("Maria@NEXOVA.example"))
    second = anonymous_client.post("/users", json=user_payload("maria@nexova.example"))

    assert first.status_code == 201
    assert "email" not in first.json()
    assert database.users_table().get(Query().email == "maria@nexova.example") is not None
    assert second.status_code == 409


def test_invalid_role_and_forged_system_fields_are_rejected(
    anonymous_client: TestClient,
):
    response = anonymous_client.post(
        "/users",
        json=user_payload(role="admin", is_active=False, hashed_password="forged"),
    )

    assert response.status_code == 422
    assert len(database.users_table()) == 0

    oversized = anonymous_client.post(
        "/users", json=user_payload(email="long@nexova.example", password="á" * 40)
    )
    assert oversized.status_code == 422


def test_login_returns_signed_jwt_and_rejects_wrong_credentials(
    anonymous_client: TestClient,
):
    user = register(anonymous_client)
    token = login(anonymous_client, user["_email"])

    assert anonymous_client.get("/auth/me", headers=bearer(token)).status_code == 200
    wrong = anonymous_client.post(
        "/auth/login",
        json={"email": user["_email"], "password": "incorrect-password"},
    )
    unknown = anonymous_client.post(
        "/auth/login",
        json={"email": "unknown@nexova.example", "password": "incorrect-password"},
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_oauth2_form_adapter_supports_swagger_authorize(anonymous_client: TestClient):
    user = register(anonymous_client)

    response = anonymous_client.post(
        "/auth/token",
        data={"username": user["_email"], "password": "SecurePassword-2026!"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert anonymous_client.get(
        "/auth/me", headers=bearer(response.json()["access_token"])
    ).status_code == 200


def test_protected_routes_reject_missing_malformed_and_expired_tokens(
    anonymous_client: TestClient,
):
    user = register(anonymous_client)
    expired = create_access_token(user["id"], expires_delta=timedelta(seconds=-1))

    missing = anonymous_client.get("/suppliers")
    malformed = anonymous_client.get("/suppliers", headers=bearer("not-a-jwt"))
    expired_response = anonymous_client.get("/suppliers", headers=bearer(expired))

    assert missing.status_code == malformed.status_code == expired_response.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"


def test_valid_token_unlocks_all_six_existing_supplier_routes(
    anonymous_client: TestClient,
):
    user = register(anonymous_client)
    headers = bearer(login(anonymous_client, user["_email"]))
    created = anonymous_client.post(
        "/suppliers",
        headers=headers,
        json={
            "name": "Auth Test Supplier",
            "country": "Spain",
            "categories": ["assessment_tools"],
            "monthly_rate": 100,
            "currency": "EUR",
            "status": "active",
        },
    )
    supplier_id = created.json()["id"]

    assert created.status_code == 201
    assert anonymous_client.get("/suppliers", headers=headers).status_code == 200
    assert anonymous_client.get(f"/suppliers/{supplier_id}", headers=headers).status_code == 200
    assert anonymous_client.patch(
        f"/suppliers/{supplier_id}/rate", headers=headers, json={"monthly_rate": 110}
    ).status_code == 200
    assert anonymous_client.patch(
        f"/suppliers/{supplier_id}/status", headers=headers, json={"status": "suspended"}
    ).status_code == 200
    assert anonymous_client.delete(f"/suppliers/{supplier_id}", headers=headers).status_code == 200


def test_auth_me_returns_safe_user_and_linked_profile(anonymous_client: TestClient):
    user = register(anonymous_client)
    response = anonymous_client.get(
        "/auth/me", headers=bearer(login(anonymous_client, user["_email"]))
    )

    assert response.status_code == 200
    assert "user_id" not in response.json()["profile"]
    assert response.json()["email"] == user["_email"]
    assert "hashed_password" not in response.text
    assert "password" not in response.text


def test_user_cannot_access_or_change_another_users_credentials(
    anonymous_client: TestClient,
):
    owner = register(anonymous_client, "owner@nexova.example")
    other = register(anonymous_client, "other@nexova.example")
    headers = bearer(login(anonymous_client, owner["_email"]))

    assert anonymous_client.get(f"/users/{other['id']}", headers=headers).status_code == 403
    assert anonymous_client.put(
        f"/users/{other['id']}", headers=headers, json={"email": "stolen@nexova.example"}
    ).status_code == 403
    assert anonymous_client.delete(f"/users/{other['id']}", headers=headers).status_code == 403


def test_user_can_update_own_credentials_but_not_role(anonymous_client: TestClient):
    user = register(anonymous_client)
    headers = bearer(login(anonymous_client, user["_email"]))

    forbidden = anonymous_client.put(
        f"/users/{user['id']}", headers=headers, json={"role": "admin"}
    )
    updated = anonymous_client.put(
        f"/users/{user['id']}",
        headers=headers,
        json={"email": "new-email@nexova.example", "password": "NewSecurePassword-2026!"},
    )

    assert forbidden.status_code == 403
    assert updated.status_code == 200
    assert updated.json()["email"] == "new-email@nexova.example"
    assert anonymous_client.post(
        "/auth/login",
        json={"email": "new-email@nexova.example", "password": "NewSecurePassword-2026!"},
    ).status_code == 200


def test_admin_can_list_and_manage_other_users(anonymous_client: TestClient):
    admin = register(anonymous_client, "admin@nexova.example")
    other = register(anonymous_client, "other@nexova.example")
    database.users_table().update({"role": "admin"}, Query().id == admin["id"])
    headers = bearer(login(anonymous_client, admin["_email"]))

    users = anonymous_client.get("/users", headers=headers)
    updated = anonymous_client.put(
        f"/users/{other['id']}", headers=headers, json={"role": "manager"}
    )

    assert users.status_code == 200
    assert len(users.json()) == 2
    assert updated.status_code == 200
    assert updated.json()["role"] == "manager"


def test_profile_owner_can_read_and_replace_contact_data(anonymous_client: TestClient):
    user = register(anonymous_client)
    headers = bearer(login(anonymous_client, user["_email"]))

    before = anonymous_client.get("/profiles/me", headers=headers)
    after = anonymous_client.put(
        "/profiles/me",
        headers=headers,
        json={"name": "María S.", "phone": "+34 600 000 099", "address": "Madrid"},
    )

    assert before.status_code == 200
    assert after.status_code == 200
    assert after.json()["name"] == "María S."
    assert "user_id" not in after.json()


def test_delete_user_also_removes_linked_profile(anonymous_client: TestClient):
    user = register(anonymous_client)
    headers = bearer(login(anonymous_client, user["_email"]))

    response = anonymous_client.delete(f"/users/{user['id']}", headers=headers)

    assert response.status_code == 204
    assert database.users_table().get(Query().id == user["id"]) is None
    assert database.profiles_table().get(Query().user_id == user["id"]) is None
