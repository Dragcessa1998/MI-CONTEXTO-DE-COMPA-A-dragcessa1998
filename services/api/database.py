"""
Inicialización de TinyDB para el Directorio de Proveedores.

TinyDB persiste en un archivo JSON junto al código: los datos sobreviven a los
reinicios del servidor (requisito de la rúbrica). Se migrará a Postgres cuando
el ORM esté listo, según la nota del tech lead.
"""

from pathlib import Path

from tinydb import TinyDB
from tinydb.table import Table

DB_PATH = Path(__file__).resolve().parent / "suppliers.db.json"

_db: TinyDB | None = None


def get_db() -> TinyDB:
    """Devuelve la instancia única de TinyDB (la crea en el primer uso)."""
    global _db
    if _db is None:
        _db = TinyDB(DB_PATH, indent=2, ensure_ascii=False)
    return _db


def suppliers_table() -> Table:
    """Tabla de proveedores."""
    return get_db().table("suppliers")


def users_table() -> Table:
    """Credenciales y autorización de usuarios (solo TinyDB)."""
    return get_db().table("users")


def profiles_table() -> Table:
    """Datos personales separados de las credenciales, enlazados por user_id."""
    return get_db().table("profiles")


def password_reset_tokens_table() -> Table:
    """Tokens de recuperación de un solo uso; solo se guarda su hash."""
    return get_db().table("password_reset_tokens")
