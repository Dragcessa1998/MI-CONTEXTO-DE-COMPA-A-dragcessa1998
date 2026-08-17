"""
Inicialización de TinyDB para el Directorio de Proveedores.

TinyDB persiste en un archivo JSON junto al código: los datos sobreviven a los
reinicios del servidor (requisito de la rúbrica). Se migrará a Postgres cuando
el ORM esté listo, según la nota del tech lead.
"""

from pathlib import Path
from threading import RLock
from typing import Any

from tinydb import TinyDB
from tinydb.table import Document, Table

DB_PATH = Path(__file__).resolve().parent / "suppliers.db.json"

_db: TinyDB | None = None
_db_lock = RLock()


class LockedTable:
    """Proxy que serializa cada operación completa de TinyDB.

    JSONStorage comparte un cursor de archivo; FastAPI ejecuta dependencias y
    handlers síncronos en varios hilos, así que dos lecturas paralelas pueden
    interferirse sin este límite.
    """

    def __init__(self, table: Table):
        self._table = table

    def all(self) -> list[Document]:
        with _db_lock:
            return self._table.all()

    def get(self, *args: Any, **kwargs: Any) -> Document | None:
        with _db_lock:
            return self._table.get(*args, **kwargs)

    def insert(self, document: Any) -> int:
        with _db_lock:
            return self._table.insert(document)

    def update(self, fields: Any, *args: Any, **kwargs: Any) -> list[int]:
        with _db_lock:
            return self._table.update(fields, *args, **kwargs)

    def remove(self, *args: Any, **kwargs: Any) -> list[int]:
        with _db_lock:
            return self._table.remove(*args, **kwargs)

    def contains(self, *args: Any, **kwargs: Any) -> bool:
        with _db_lock:
            return self._table.contains(*args, **kwargs)

    def __len__(self) -> int:
        with _db_lock:
            return len(self._table)


def get_db() -> TinyDB:
    """Devuelve la instancia única de TinyDB (la crea en el primer uso)."""
    global _db
    with _db_lock:
        if _db is None:
            _db = TinyDB(DB_PATH, indent=2, ensure_ascii=False)
        return _db


def suppliers_table() -> LockedTable:
    """Tabla de proveedores."""
    return LockedTable(get_db().table("suppliers"))


def users_table() -> LockedTable:
    """Credenciales y autorización de usuarios (solo TinyDB)."""
    return LockedTable(get_db().table("users"))


def profiles_table() -> LockedTable:
    """Datos personales separados de las credenciales, enlazados por user_id."""
    return LockedTable(get_db().table("profiles"))


def incidents_table() -> LockedTable:
    """Incidentes operativos centralizados de Nexova."""
    return LockedTable(get_db().table("incidents"))
