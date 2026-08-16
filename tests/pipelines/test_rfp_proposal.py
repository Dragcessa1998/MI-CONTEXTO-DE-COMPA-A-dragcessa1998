from __future__ import annotations

from typing import Any

import data.pipelines.rfp_intake.proposal as proposal
from data.pipelines.rfp_intake.models import RfpMetadata
from data.pipelines.rfp_intake.proposal_models import EvaluationResult


def _ticket() -> dict[str, Any]:
    return {
        "ticket_id": "ticket-vantex",
        "status": "intake_complete",
        "metadata": {
            "client_name": "Vantex Retail Group, S.A.",
            "client_hq": "España",
            "currency": "EUR",
            "services_requested": ["búsqueda ejecutiva", "formación corporativa"],
            "scope": "Cinco posiciones y formación de liderazgo.",
            "volumes": {"roles": 5, "participants": 40},
            "deadline": "2026-08-18",
            "budget_range": None,
            "departments_needed": ["seleccion", "capacitacion"],
            "readability": {
                "word_count": 20,
                "sentence_count": 2,
                "average_words_per_sentence": 10.0,
                "flesch_reading_ease": 60.0,
                "gunning_fog": 9.0,
            },
        },
        "sections": [
            {
                "department_id": "seleccion",
                "department_name": "Talent Selection Operations",
                "contact": "Javier Almeida",
                "key_aspects": ["Cubrir 5 roles de mandos medios."],
                "open_questions": ["Confirmar presupuesto."],
                "relevant_excerpts": ["Se requieren 5 roles."],
            },
            {
                "department_id": "capacitacion",
                "department_name": "Corporate Training",
                "contact": "Elena Vargas",
                "key_aspects": ["Programa de liderazgo para 40 participantes."],
                "open_questions": ["Confirmar presupuesto."],
                "relevant_excerpts": ["Se formarán 40 participantes."],
            },
        ],
    }


def test_generator_uses_part_one_handoff_and_department_rules() -> None:
    result = proposal.run_proposal_generation(_ticket())

    assert result.status == "under_evaluation"
    assert {section.department_id for section in result.sections} == {"seleccion", "capacitacion"}
    selection = next(item for item in result.sections if item.department_id == "seleccion")
    assert "5 roles de mandos medios" in selection.draft_content
    assert "al menos 15 días laborables" in selection.draft_content
    assert "EUR" in selection.draft_content
    assert "90 días" in selection.draft_content
    assert selection.evaluation_results[-1].overall_pass is True


def test_compliance_evaluator_is_anchored_to_nexova_rules() -> None:
    metadata = RfpMetadata.model_validate(_ticket()["metadata"])
    result = proposal.evaluate_compliance(
        "Ofrecemos selección ejecutiva en USD y entrega en 5 días.",
        "seleccion",
        metadata,
    )

    assert result.passed is False
    assert set(result.rule_ids) == {"G-90", "CUR-01", "REF-ANON", "SEL-15"}
    assert any(item.startswith("G-90") for item in result.violations)
    assert any(item.startswith("CUR-01") for item in result.violations)
    assert any(item.startswith("SEL-15") for item in result.violations)


def test_iteration_limit_keeps_last_draft_for_human_review(monkeypatch) -> None:
    def always_fail(
        _draft: str,
        department_id: str,
        _metadata: RfpMetadata,
        _key_aspects: list[str],
        iteration: int,
    ) -> EvaluationResult:
        return EvaluationResult.model_validate({
            "section_id": department_id,
            "readability": {"pass": False, "score": 20, "details": "Demasiado compleja."},
            "relevance": {"pass": True, "missing_aspects": []},
            "compliance": {"pass": True, "rule_ids": ["G-90"], "violations": []},
            "overall_pass": False,
            "actionable_feedback": ["Acortar frases."],
            "iteration": iteration,
        })

    monkeypatch.setattr(proposal, "evaluate_section_parallel", always_fail)
    failing_graph = proposal.build_proposal_graph()

    result = proposal.run_proposal_generation(_ticket(), max_iterations=2, graph=failing_graph)

    assert result.status == "needs_human_review"
    assert all(section.needs_human_review for section in result.sections)
    assert all(section.generation_iteration == 2 for section in result.sections)
    assert all(len(section.evaluation_results) == 2 for section in result.sections)
    assert all(section.draft_content for section in result.sections)


def test_support_evaluator_rejects_missing_24_hour_sla() -> None:
    metadata_data = _ticket()["metadata"] | {
        "client_name": "NubeSoft",
        "client_hq": "Miami",
        "currency": "USD",
        "departments_needed": ["soporte"],
    }
    metadata = RfpMetadata.model_validate(metadata_data)

    result = proposal.evaluate_compliance(
        "Soporte por turnos. Garantía de satisfacción de 90 días. Precio en USD.",
        "soporte",
        metadata,
    )

    assert result.passed is False
    assert any(item.startswith("SUP-24") for item in result.violations)
