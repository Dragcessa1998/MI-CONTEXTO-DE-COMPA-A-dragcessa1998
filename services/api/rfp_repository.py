"""Persistencia PostgreSQL/Supabase para tickets y análisis RFP."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from data.pipelines.rfp_intake.models import IntakeResult


MIGRATION_PATH = Path(__file__).resolve().parent / "migrations" / "002_create_rfp_intake.sql"


class RfpRepository(Protocol):
    def create_ticket(self, raw_pdf_path: str) -> dict[str, Any]: ...
    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None: ...
    def list_tickets(self) -> list[dict[str, Any]]: ...
    def save_result(self, ticket_id: str, result: IntakeResult) -> None: ...
    def mark_failed(self, ticket_id: str) -> None: ...


class PostgresRfpRepository:
    """Fuente de verdad RFP; rechaza SQLite/TinyDB por diseño."""

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith(("postgresql://", "postgres://")):
            raise ValueError("Las RFP requieren DATABASE_URL PostgreSQL/Supabase")
        self.database_url = database_url
        self.initialize()

    def _connect(self):
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(self.database_url, row_factory=dict_row)

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(MIGRATION_PATH.read_text(encoding="utf-8"))
            connection.commit()

    def create_ticket(self, raw_pdf_path: str) -> dict[str, Any]:
        ticket_id, rfp_id = str(uuid4()), str(uuid4())
        with self._connect() as connection:
            row = connection.execute(
                "INSERT INTO rfp_tickets (ticket_id,rfp_id,status,raw_pdf_path) "
                "VALUES (%s,%s,'analyzing',%s) RETURNING *",
                (ticket_id, rfp_id, raw_pdf_path),
            ).fetchone()
            connection.commit()
        return self._hydrate(row, None, [])

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            ticket = connection.execute(
                "SELECT * FROM rfp_tickets WHERE ticket_id=%s",
                (ticket_id,),
            ).fetchone()
            if ticket is None:
                return None
            metadata = connection.execute(
                "SELECT * FROM rfp_metadata WHERE rfp_id=%s",
                (ticket["rfp_id"],),
            ).fetchone()
            sections = connection.execute(
                "SELECT department_id,department_name,contact,key_aspects,open_questions,relevant_excerpts "
                "FROM rfp_department_sections WHERE rfp_id=%s ORDER BY department_id",
                (ticket["rfp_id"],),
            ).fetchall()
        return self._hydrate(ticket, metadata, sections)

    def list_tickets(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM rfp_tickets ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
        return [self._hydrate(row, None, []) for row in rows]

    def save_result(self, ticket_id: str, result: IntakeResult) -> None:
        from psycopg.types.json import Jsonb

        status = "intake_complete" if result.classification.is_rfp else "discarded"
        with self._connect() as connection:
            ticket = connection.execute(
                "SELECT rfp_id FROM rfp_tickets WHERE ticket_id=%s FOR UPDATE",
                (ticket_id,),
            ).fetchone()
            if ticket is None:
                raise KeyError("ticket inexistente")
            rfp_id = ticket["rfp_id"]
            connection.execute(
                "UPDATE rfp_tickets SET status=%s,markdown_path=%s,classification_reason=%s,"
                "sales_summary=%s,processing_error=NULL,updated_at=NOW() WHERE ticket_id=%s",
                (
                    status,
                    result.markdown_path,
                    result.classification.reason,
                    result.sales_summary,
                    ticket_id,
                ),
            )
            if result.metadata is not None:
                metadata = result.metadata
                connection.execute(
                    "INSERT INTO rfp_metadata (rfp_id,client_name,client_hq,currency,services_requested,scope,volumes,deadline,budget_range,departments_needed,readability) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (rfp_id) DO UPDATE SET client_name=EXCLUDED.client_name,client_hq=EXCLUDED.client_hq,currency=EXCLUDED.currency,services_requested=EXCLUDED.services_requested,scope=EXCLUDED.scope,volumes=EXCLUDED.volumes,deadline=EXCLUDED.deadline,budget_range=EXCLUDED.budget_range,departments_needed=EXCLUDED.departments_needed,readability=EXCLUDED.readability",
                    (
                        rfp_id,
                        metadata.client_name,
                        metadata.client_hq,
                        metadata.currency,
                        Jsonb(metadata.services_requested),
                        metadata.scope,
                        Jsonb(metadata.volumes),
                        metadata.deadline,
                        metadata.budget_range,
                        Jsonb(metadata.departments_needed),
                        Jsonb(metadata.readability.model_dump()),
                    ),
                )
                connection.execute("DELETE FROM rfp_department_sections WHERE rfp_id=%s", (rfp_id,))
                for section in result.sections:
                    connection.execute(
                        "INSERT INTO rfp_department_sections (id,rfp_id,department_id,department_name,contact,key_aspects,open_questions,relevant_excerpts) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            str(uuid4()), rfp_id, section.department_id, section.department_name,
                            section.contact, Jsonb(section.key_aspects), Jsonb(section.open_questions),
                            Jsonb(section.relevant_excerpts),
                        ),
                    )
            connection.commit()

    def mark_failed(self, ticket_id: str) -> None:
        """Conserva `analyzing` pero señala que ya no hay job activo para permitir retry."""
        with self._connect() as connection:
            connection.execute(
                "UPDATE rfp_tickets SET processing_error='processing_failed',updated_at=NOW() WHERE ticket_id=%s",
                (ticket_id,),
            )
            connection.commit()

    @staticmethod
    def _hydrate(ticket: Any, metadata: Any, sections: list[Any]) -> dict[str, Any]:
        data = dict(ticket)
        for key in ("ticket_id", "rfp_id"):
            data[key] = str(data[key])
        for key in ("created_at", "updated_at"):
            if data.get(key) is not None:
                data[key] = data[key].isoformat()
        data["metadata"] = dict(metadata) if metadata else None
        if data["metadata"]:
            data["metadata"].pop("rfp_id", None)
        data["sections"] = [dict(section) for section in sections]
        return data


@lru_cache(maxsize=1)
def get_rfp_repository() -> PostgresRfpRepository:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL PostgreSQL/Supabase es obligatorio para RFPs")
    return PostgresRfpRepository(database_url)
