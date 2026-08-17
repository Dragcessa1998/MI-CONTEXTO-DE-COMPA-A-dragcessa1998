"""Hash de contraseñas, firma JWT y dependencia de autenticación FastAPI."""

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.hash import bcrypt

from auth_models import UserRecord


ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def access_token_expire_minutes() -> int:
    raw_value = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES debe ser un entero") from exc
    if value <= 0:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES debe ser mayor que 0")
    return value


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET no está configurado")
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET debe tener al menos 32 caracteres")
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.verify(password, hashed_password)
    except (TypeError, ValueError):
        return False


def create_access_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=access_token_expire_minutes())
    )
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": expires_at},
        _jwt_secret(),
        algorithm=ALGORITHM,
    )


def password_reset_expire_minutes() -> int:
    raw_value = os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30")
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("PASSWORD_RESET_EXPIRE_MINUTES debe ser un entero") from exc
    if not 15 <= value <= 60:
        raise RuntimeError("PASSWORD_RESET_EXPIRE_MINUTES debe estar entre 15 y 60")
    return value


def create_password_reset_token(
    user_id: int,
    token_id: str,
    expires_delta: timedelta | None = None,
) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=password_reset_expire_minutes())
    )
    token = jwt.encode(
        {
            "sub": str(user_id),
            "jti": token_id,
            "purpose": "password-reset",
            "iat": now,
            "exp": expires_at,
        },
        _jwt_secret(),
        algorithm=ALGORITHM,
    )
    return token, expires_at


def decode_password_reset_token(token: str) -> tuple[int, str]:
    try:
        payload: dict[str, Any] = jwt.decode(token, _jwt_secret(), algorithms=[ALGORITHM])
        if payload.get("purpose") != "password-reset":
            raise JWTError("Propósito de token incorrecto")
        subject = payload.get("sub")
        token_id = payload.get("jti")
        if not isinstance(subject, str) or not isinstance(token_id, str):
            raise JWTError("Token incompleto")
        return int(subject), token_id
    except (JWTError, TypeError, ValueError) as exc:
        raise ValueError("Token de recuperación inválido o expirado") from exc


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(token: str = Depends(oauth2_scheme)) -> UserRecord:
    """Valida firma, expiración, subject y existencia/estado del usuario."""
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[ALGORITHM])
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise unauthorized()
        user_id = int(subject)
    except (JWTError, TypeError, ValueError):
        raise unauthorized()

    # Importación local: evita un ciclo entre el servicio (hash) y la dependencia.
    from auth_service import get_user_by_id

    user = get_user_by_id(user_id)
    if user is None or not user.is_active:
        raise unauthorized()
    return user
