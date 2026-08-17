"""Unit tests for OAuth2 token creation and validation."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from jose import jwt
from tinydb import Query

import database
from auth_models import UserCreate
from auth_service import create_user
from routes.auth import oauth2_token
from security import (
    ALGORITHM,
    _jwt_secret,
    access_token_expire_minutes,
    create_access_token,
    get_current_user,
)


PASSWORD = "ReliablePassword-2026!"


def create_account(email: str = "token@nexova.example"):
    user, _profile = create_user(
        UserCreate(email=email, password=PASSWORD, name="Token Test")
    )
    return user


def assert_unauthorized(token: str) -> None:
    with pytest.raises(HTTPException) as error:
        get_current_user(token)
    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


def test_oauth2_adapter_returns_token_for_valid_form_credentials() -> None:
    """Happy path: Swagger's form adapter uses the same authentication rules."""
    user = create_account()
    form = SimpleNamespace(username=" TOKEN@NEXOVA.EXAMPLE ", password=PASSWORD)

    result = oauth2_token(form)

    assert result.expires_in == 1800
    assert get_current_user(result.access_token).id == user.id


def test_expired_token_is_rejected() -> None:
    """Edge case found during AI review: expiration must be tested explicitly."""
    user = create_account()
    expired = create_access_token(user.id, expires_delta=timedelta(seconds=-1))

    assert_unauthorized(expired)


@pytest.mark.parametrize("token", ["not-a-jwt", "", "eyJhbGciOiJub25lIn0.e30."])
def test_malformed_tokens_are_rejected(token: str) -> None:
    """Failure mode: malformed input never escapes as an internal exception."""
    assert_unauthorized(token)


def test_token_without_subject_is_rejected() -> None:
    token = jwt.encode({"purpose": "not-authentication"}, _jwt_secret(), algorithm=ALGORITHM)
    assert_unauthorized(token)


def test_token_for_missing_or_inactive_user_is_rejected() -> None:
    user = create_account()
    inactive_token = create_access_token(user.id)
    database.users_table().update({"is_active": False}, Query().id == user.id)
    assert_unauthorized(inactive_token)

    assert_unauthorized(create_access_token(999_999))


@pytest.mark.parametrize("value", ["zero", "0", "-1"])
def test_invalid_expiration_configuration_fails_safely(monkeypatch, value: str) -> None:
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", value)
    with pytest.raises(RuntimeError):
        access_token_expire_minutes()


@pytest.mark.parametrize("secret", ["", "too-short"])
def test_missing_or_short_jwt_secret_fails_safely(monkeypatch, secret: str) -> None:
    if secret:
        monkeypatch.setenv("JWT_SECRET", secret)
    else:
        monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        _jwt_secret()
