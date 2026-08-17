"""Entrega de emails transaccionales con Resend, sin persistir secretos."""

import json
import logging
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)
RESEND_ENDPOINT = "https://api.resend.com/emails"


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} no está configurado")
    return value


def send_password_reset_email(recipient: str, token: str) -> None:
    api_key = _required_env("RESEND_API_KEY")
    sender = _required_env("PASSWORD_RESET_FROM_EMAIL")
    frontend_url = os.getenv(
        "PASSWORD_RESET_FRONTEND_URL", "http://localhost:3000/reset-password"
    ).strip()
    separator = "&" if "?" in frontend_url else "?"
    reset_url = f"{frontend_url}{separator}{urlencode({'token': token})}"
    payload = {
        "from": sender,
        "to": [recipient],
        "subject": "Restablece tu contraseña de Nexova",
        "html": (
            '<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;padding:24px">'
            '<h1 style="font-size:24px">Restablece tu contraseña</h1>'
            "<p>Recibimos una solicitud para cambiar la contraseña de tu cuenta.</p>"
            f'<p><a href="{reset_url}" style="display:inline-block;padding:12px 18px;'
            'background:#2563eb;color:white;text-decoration:none;border-radius:8px">'
            "Crear una contraseña nueva</a></p>"
            "<p>Este enlace caduca pronto y solo puede utilizarse una vez.</p>"
            "<p>Si no solicitaste el cambio, puedes ignorar este mensaje.</p></div>"
        ),
    }
    request = Request(
        RESEND_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Nexova-Auth/1.0",
        },
    )
    with urlopen(request, timeout=10) as response:  # noqa: S310 - endpoint is constant
        if response.status >= 400:
            raise RuntimeError("Resend rechazó el email de recuperación")


def try_send_password_reset_email(recipient: str, token: str) -> None:
    try:
        send_password_reset_email(recipient, token)
    except Exception:
        logger.exception("No se pudo entregar el email de recuperación")
