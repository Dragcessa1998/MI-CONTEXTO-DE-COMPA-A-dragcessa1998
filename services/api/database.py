"""Conexiones de Nexova: TinyDB para identidad y SQLModel para inventario."""

import os
from collections.abc import Generator
from pathlib import Path
from threading import RLock
from typing import Any

from sqlmodel import Session, SQLModel, create_engine
from tinydb import TinyDB
from tinydb.table import Document, Table

DB_PATH = Path(__file__).resolve().parent / "suppliers.db.json"
INVENTORY_DB_PATH = Path(__file__).resolve().parent / "inventory.db"

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


def get_tinydb() -> TinyDB:
    """Devuelve la instancia única de TinyDB (la crea en el primer uso)."""
    global _db
    with _db_lock:
        if _db is None:
            _db = TinyDB(DB_PATH, indent=2, ensure_ascii=False)
        return _db


def suppliers_table() -> LockedTable:
    """Tabla de proveedores."""
    return LockedTable(get_tinydb().table("suppliers"))


def users_table() -> LockedTable:
    """Credenciales y autorización de usuarios (solo TinyDB)."""
    return LockedTable(get_tinydb().table("users"))


def profiles_table() -> LockedTable:
    """Datos personales separados de las credenciales, enlazados por user_id."""
    return LockedTable(get_tinydb().table("profiles"))


def incidents_table() -> LockedTable:
    """Incidentes operativos centralizados de Nexova."""
    return LockedTable(get_tinydb().table("incidents"))


def _inventory_database_url() -> str:
    configured = os.getenv("DATABASE_URL", "").strip()
    if configured:
        # SQLAlchemy 2 expects the explicit postgresql scheme.
        if configured.startswith("postgres://"):
            return "postgresql://" + configured.removeprefix("postgres://")
        return configured
    return f"sqlite:///{INVENTORY_DB_PATH}"


def _build_inventory_engine(database_url: str):
    options: dict[str, Any] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    return create_engine(database_url, **options)


# El engine puede ser global; la sesión no. Cada petición recibe una sesión nueva.
inventory_engine = _build_inventory_engine(_inventory_database_url())


def get_db() -> Generator[Session, None, None]:
    """Inyecta una sesión SQLModel por petición para los datos de inventario."""
    with Session(inventory_engine) as session:
        yield session


def create_inventory_schema() -> None:
    """Crea las tablas ORM en Supabase (o SQLite local) al arrancar."""
    import inventory_models  # noqa: F401 -- registra modelos en metadata

    SQLModel.metadata.create_all(inventory_engine)
