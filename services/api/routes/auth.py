"""Inicio de sesión JWT y proyección segura del usuario autenticado."""

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from auth_models import LoginRequest, TokenResponse, UserOut, UserRecord, UserWithProfile
from auth_service import get_profile_by_user_id, get_user_by_email
from security import (
    access_token_expire_minutes,
    create_access_token,
    get_current_user,
    unauthorized,
    verify_password,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _authenticate(email: str, password: str) -> TokenResponse:
    user = get_user_by_email(email)
    if user is None or not user.is_active or not verify_password(password, user.hashed_password):
        raise unauthorized()
    expires_in = access_token_expire_minutes() * 60
    return TokenResponse(
        access_token=create_access_token(user.id, role=user.role),
        expires_in=expires_in,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    """Login JSON para el backoffice y otros clientes de la API."""
    return _authenticate(str(payload.email), payload.password)


@router.post("/token", response_model=TokenResponse)
def oauth2_token(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """Adaptador OAuth2 estándar usado por el botón Authorize de Swagger."""
    return _authenticate(form.username.strip().lower(), form.password)


@router.get("/me", response_model=UserWithProfile)
def read_auth_me(current_user: UserRecord = Depends(get_current_user)) -> UserWithProfile:
    profile = get_profile_by_user_id(current_user.id)
    if profile is None:
        raise unauthorized()
    safe_user = UserOut.model_validate(current_user.model_dump())
    return UserWithProfile(**safe_user.model_dump(), profile=profile)
