"""Contrato de persistencia RFP ejecutable contra PostgreSQL real."""

from __future__ import annotations

import os

import pytest

from data.pipelines.rfp_intake.models import IntakeResult
from rfp_repository import PostgresRfpRepository


DATABASE_URL = os.getenv("TEST_POSTGRES_DATABASE_URL")


def test_repository_rejects_non_postgres_databases() -> None:
    with pytest.raises(ValueError, match="PostgreSQL/Supabase"):
        PostgresRfpRepository("sqlite:///rfps.db")


@pytest.mark.skipif(not DATABASE_URL, reason="TEST_POSTGRES_DATABASE_URL no configurada")
def test_repository_round_trip_in_real_postgres() -> None:
    repository = PostgresRfpRepository(DATABASE_URL or "")
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
    assert persisted["status"] == "analisis_completo"
    assert persisted["metadata"]["volumes"] == {"roles": 5, "participants": 40}
    assert {section["contact"] for section in persisted["sections"]} == {
        "Javier Almeida",
        "Elena Vargas",
    }
    assert repository.list_tickets()[0]["ticket_id"] == ticket["ticket_id"]

    with repository._connect() as connection:
        connection.execute("TRUNCATE rfp_tickets CASCADE")
        connection.commit()
