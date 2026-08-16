"""Hash de contraseñas, firma JWT y dependencia de autenticación FastAPI."""

import os
from datetime import datetime, timedelta, timezone

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


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_user_from_token(token: str) -> UserRecord:
    """Valida un JWT reutilizable por HTTP, SSE y WebSocket."""

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


def get_current_user(token: str = Depends(oauth2_scheme)) -> UserRecord:
    """Dependencia HTTP sobre el mismo validador usado por WebSocket."""

    return get_user_from_token(token)
