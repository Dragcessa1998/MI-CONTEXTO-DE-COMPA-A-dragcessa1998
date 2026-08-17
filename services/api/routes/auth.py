"""Inicio de sesión JWT y proyección segura del usuario autenticado."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from auth_models import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
    UserRecord,
    UserWithProfile,
)
from auth_service import (
    PasswordResetTokenError,
    consume_password_reset_token,
    get_profile_by_user_id,
    get_user_by_email,
    invalidate_password_reset_tokens,
    issue_password_reset_token,
    set_user_password,
)
from email_service import try_send_password_reset_email
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
        access_token=create_access_token(user.id),
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


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
) -> MessageResponse:
    user = get_user_by_email(str(payload.email))
    if user is not None and user.is_active:
        token = issue_password_reset_token(user.id)
        background_tasks.add_task(try_send_password_reset_email, str(user.email), token)
    return MessageResponse(
        message="Si la dirección está registrada, recibirás un enlace en breve."
    )


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest) -> MessageResponse:
    try:
        consume_password_reset_token(payload.token, payload.new_password)
    except PasswordResetTokenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageResponse(message="Contraseña restablecida correctamente.")


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    current_user: UserRecord = Depends(get_current_user),
) -> MessageResponse:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta")
    set_user_password(current_user.id, payload.new_password)
    invalidate_password_reset_tokens(current_user.id)
    return MessageResponse(message="Contraseña actualizada correctamente.")
