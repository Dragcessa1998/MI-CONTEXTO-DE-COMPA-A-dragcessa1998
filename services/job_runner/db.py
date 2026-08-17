"""Adaptador DB-API mínimo para PostgreSQL en producción y SQLite en pruebas."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class RelationalDatabase:
    """Abre conexiones sin acoplar la lógica de jobs a un framework web."""

    def __init__(self, database_url: str):
        if database_url.startswith("sqlite:///"):
            raw_path = database_url.removeprefix("sqlite:///")
            if raw_path == ":memory:":
                raise ValueError("SQLite en memoria no sirve para procesos independientes")
            self.kind = "sqlite"
            self.path = Path(raw_path).expanduser().resolve()
        elif database_url.startswith(("postgresql://", "postgres://")):
            self.kind = "postgres"
            self.path = None
        else:
            raise ValueError("DATABASE_URL debe usar sqlite:/// o postgresql://")
        self.database_url = database_url

    @property
    def placeholder(self) -> str:
        return "?" if self.kind == "sqlite" else "%s"

    def connect(self) -> Any:
        if self.kind == "sqlite":
            assert self.path is not None
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout = 10000")
            connection.execute("PRAGMA foreign_keys = ON")
            return connection

        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL requiere instalar services/job_runner/requirements.txt"
            ) from exc
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def begin_write(self, connection: Any) -> None:
        if self.kind == "sqlite":
            connection.execute("BEGIN IMMEDIATE")
        else:
            connection.execute("BEGIN")

    @staticmethod
    def is_unique_violation(error: BaseException) -> bool:
        if isinstance(error, sqlite3.IntegrityError):
            return "UNIQUE constraint failed" in str(error)
        return getattr(error, "sqlstate", None) == "23505"
