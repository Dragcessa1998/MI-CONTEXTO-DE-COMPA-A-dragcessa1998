"""Contrato de persistencia RFP ejecutable contra PostgreSQL real."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from data.pipelines.rfp_intake.models import IntakeResult
from data.pipelines.rfp_intake.approval import generate_final_document
from data.pipelines.rfp_intake.approval_models import ApprovalBranchResult
from data.pipelines.rfp_intake.proposal import run_proposal_generation
from rfp_repository import PostgresRfpRepository


DATABASE_URL = os.getenv("TEST_POSTGRES_DATABASE_URL")


def test_repository_rejects_non_postgres_databases() -> None:
    with pytest.raises(ValueError, match="PostgreSQL/Supabase"):
        PostgresRfpRepository("sqlite:///rfps.db")


@pytest.mark.skipif(not DATABASE_URL, reason="TEST_POSTGRES_DATABASE_URL no configurada")
def test_repository_round_trip_in_real_postgres(tmp_path: Path) -> None:
    repository = PostgresRfpRepository(DATABASE_URL or "")
    with repository._connect() as connection:
        connection.execute("TRUNCATE rfp_tickets CASCADE")
        connection.commit()


@pytest.mark.skipif(not DATABASE_URL, reason="TEST_POSTGRES_DATABASE_URL no configurada")
def test_legacy_spanish_statuses_are_migrated() -> None:
    import psycopg

    with psycopg.connect(DATABASE_URL or "") as connection:
        connection.execute("DROP TABLE IF EXISTS rfp_department_sections, rfp_metadata, rfp_tickets CASCADE")
        connection.execute(
            "CREATE TABLE rfp_tickets ("
            "ticket_id UUID PRIMARY KEY, rfp_id UUID NOT NULL UNIQUE, "
            "status TEXT NOT NULL CHECK (status IN ('analizando','descartado','analisis_completo')), "
            "raw_pdf_path TEXT NOT NULL, markdown_path TEXT, classification_reason TEXT, "
            "sales_summary TEXT, processing_error TEXT, "
            "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
        )
        for status in ("analizando", "descartado", "analisis_completo"):
            connection.execute(
                "INSERT INTO rfp_tickets (ticket_id,rfp_id,status,raw_pdf_path) VALUES (%s,%s,%s,%s)",
                (str(uuid4()), str(uuid4()), status, f"/tmp/{status}.pdf"),
            )
        connection.commit()

    repository = PostgresRfpRepository(DATABASE_URL or "")
    assert {ticket["status"] for ticket in repository.list_tickets()} == {
        "analyzing",
        "discarded",
        "intake_complete",
    }

    with repository._connect() as connection:
        connection.execute("TRUNCATE rfp_tickets CASCADE")
        connection.commit()

    ticket = repository.create_ticket("/tmp/vantex.pdf")
    result = IntakeResult.model_validate({
        "classification": {"is_rfp": True, "reason": "Solicitud de propuesta válida."},
        "metadata": {
            "client_name": "Vantex Retail Group, S.A.",
            "client_hq": "España",
            "currency": "EUR",
            "services_requested": ["búsqueda ejecutiva", "formación corporativa"],
            "scope": "Cinco posiciones y formación para cuarenta participantes.",
            "volumes": {"roles": 5, "participants": 40},
            "deadline": "2026-08-18",
            "budget_range": None,
            "departments_needed": ["seleccion", "capacitacion"],
            "readability": {
                "word_count": 8,
                "sentence_count": 1,
                "average_words_per_sentence": 8.0,
                "flesch_reading_ease": 42.0,
                "gunning_fog": 12.0,
            },
        },
        "sections": [
            {
                "department_id": "seleccion",
                "department_name": "Talent Selection Operations",
                "contact": "Javier Almeida",
                "key_aspects": ["Cubrir cinco posiciones."],
                "open_questions": ["Confirmar presupuesto."],
                "relevant_excerpts": ["Cinco posiciones."],
            },
            {
                "department_id": "capacitacion",
                "department_name": "Corporate Training",
                "contact": "Elena Vargas",
                "key_aspects": ["Formar cuarenta participantes."],
                "open_questions": ["Confirmar presupuesto."],
                "relevant_excerpts": ["Cuarenta participantes."],
            },
        ],
        "sales_summary": "Propuesta coordinada por Javier Almeida y Elena Vargas.",
        "markdown_path": "/tmp/vantex.md",
    })
    repository.save_result(ticket["ticket_id"], result)

    persisted = repository.get_ticket(ticket["ticket_id"])
    assert persisted is not None
    assert persisted["status"] == "intake_complete"
    assert persisted["metadata"]["volumes"] == {"roles": 5, "participants": 40}
    assert {section["contact"] for section in persisted["sections"]} == {
        "Javier Almeida",
        "Elena Vargas",
    }
    assert repository.list_tickets()[0]["ticket_id"] == ticket["ticket_id"]

    repository.start_drafting(ticket["ticket_id"])
    repository.mark_under_evaluation(ticket["ticket_id"])
    repository.save_generation(ticket["ticket_id"], run_proposal_generation(persisted))
    generated = repository.get_ticket(ticket["ticket_id"])
    assert generated is not None
    assert generated["status"] == "under_evaluation"
    assert all(section["draft_content"] for section in generated["sections"])
    assert all(section["evaluation_results"][-1]["overall_pass"] for section in generated["sections"])
    assert all(section["generation_iteration"] == 1 for section in generated["sections"])

    waiting = repository.start_approvals(ticket["ticket_id"])
    assert waiting["status"] == "waiting_for_approval"
    for section in waiting["sections"]:
        repository.save_approval_branch(ApprovalBranchResult(
            ticket_id=ticket["ticket_id"],
            department_id=section["department_id"],
            thread_id=f"rfp-{ticket['ticket_id']}:{section['department_id']}",
            approval_status="approved",
            approval_iteration=0,
            draft_content=section["draft_content"],
            interrupted=False,
        ))
    approved = repository.get_ticket(ticket["ticket_id"])
    assert approved is not None
    document = generate_final_document(approved, tmp_path)
    repository.save_final_document(document)
    assert repository.get_ticket(ticket["ticket_id"])["status"] == "done"
    assert repository.get_final_document(ticket["ticket_id"])["currency"] == "EUR"

    reloaded_repository = PostgresRfpRepository(DATABASE_URL or "")
    assert reloaded_repository.get_ticket(ticket["ticket_id"])["status"] == "done"

    with repository._connect() as connection:
        connection.execute("TRUNCATE rfp_tickets CASCADE")
        connection.commit()
