"""Unit tests for login business rules (POST /auth/login)."""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from tinydb import Query

import database
from auth_models import LoginRequest, UserCreate
from auth_service import create_user
from routes.auth import _authenticate, login
from security import get_current_user


PASSWORD = "ReliablePassword-2026!"


def create_account(email: str = "login@nexova.example"):
    user, _profile = create_user(
        UserCreate(email=email, password=PASSWORD, name="Login Test")
    )
    return user


def test_login_returns_a_signed_token_with_expected_lifetime() -> None:
    """Happy path: the endpoint delegates to authentication and signs a JWT."""
    user = create_account()

    result = login(LoginRequest(email=user.email, password=PASSWORD))

    assert result.token_type == "bearer"
    assert result.expires_in == 30 * 60
    assert get_current_user(result.access_token).id == user.id


def test_login_normalizes_email_whitespace_and_case() -> None:
    """Edge case: a human-entered email still identifies the same account."""
    user = create_account("case@nexova.example")

    result = _authenticate("  CASE@NEXOVA.EXAMPLE ", PASSWORD)

    assert get_current_user(result.access_token).id == user.id


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("login@nexova.example", "wrong-password"),
        ("missing@nexova.example", "wrong-password"),
    ],
)
def test_login_rejects_wrong_or_unknown_credentials_without_user_disclosure(
    email: str, password: str
) -> None:
    """Failure modes deliberately share the same public 401 response."""
    create_account()

    with pytest.raises(HTTPException) as error:
        _authenticate(email, password)

    assert error.value.status_code == 401
    assert error.value.detail == "No se pudieron validar las credenciales"


def test_login_rejects_an_inactive_account() -> None:
    """Failure mode: valid credentials cannot reactivate a disabled account."""
    user = create_account()
    database.users_table().update({"is_active": False}, Query().id == user.id)

    with pytest.raises(HTTPException) as error:
        _authenticate(str(user.email), PASSWORD)

    assert error.value.status_code == 401


def test_login_model_rejects_empty_password() -> None:
    """Boundary input is rejected by the authentication contract."""
    with pytest.raises(ValidationError):
        LoginRequest(email="login@nexova.example", password="")
