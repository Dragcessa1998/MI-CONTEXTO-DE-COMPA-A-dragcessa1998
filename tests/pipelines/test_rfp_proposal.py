from __future__ import annotations

import threading
from typing import Any, Callable

import pytest

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


def _aspects(prompt: str) -> str:
    return prompt.split("Aspectos clave:\n", 1)[1].split("\n\n", 1)[0]


def passing_draft(prompt: str) -> str:
    currency = prompt.split("Divisa: ", 1)[1].split("\n", 1)[0]
    return (
        f"## Propuesta\n\n{_aspects(prompt)}\n\nCotizamos en {currency}. "
        "Incluye la garantía de satisfacción de 90 días. "
        "Cada búsqueda ejecutiva dura al menos 15 días laborables. "
        "El SLA de respuesta es de 24 horas."
    )


def failing_draft(prompt: str) -> str:
    # Cubre los aspectos, pero sin garantía, sin divisa y con un plazo prohibido.
    return f"## Propuesta\n\n{_aspects(prompt)}\n\nEntregamos en 5 días."


class FakeLLM:
    """LLM falso: registra cada llamada y responde según la n-ésima llamada del departamento."""

    def __init__(self, script: Callable[[int], Callable[[str], str]]) -> None:
        self.script = script
        self.calls: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def __call__(self, instructions: str, prompt: str) -> str:
        with self._lock:
            self.calls.append((instructions, prompt))
            nth = sum(1 for item, _ in self.calls if item == instructions)
        return self.script(nth)(prompt)

    def calls_for(self, department_id: str) -> list[str]:
        marker = proposal.DEPARTMENT_AGENTS[department_id]
        return [prompt for instructions, prompt in self.calls if instructions.startswith(marker)]


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    llm = FakeLLM(lambda _n: passing_draft)
    monkeypatch.setattr(proposal, "call_llm", llm)
    return llm


def test_generator_uses_part_one_handoff_and_department_rules(fake_llm: FakeLLM) -> None:
    result = proposal.run_proposal_generation(_ticket())

    assert result.status == "under_evaluation"
    assert {section.department_id for section in result.sections} == {"seleccion", "capacitacion"}
    selection = next(item for item in result.sections if item.department_id == "seleccion")
    first_prompt = fake_llm.calls_for("seleccion")[0]
    assert "5 roles de mandos medios" in first_prompt
    assert "Divisa: EUR" in first_prompt
    assert selection.evaluation_results[-1].overall_pass is True
    assert selection.generation_iteration == 1


def test_failing_drafts_iterate_until_compliance_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = FakeLLM(lambda n: failing_draft if n < 3 else passing_draft)
    monkeypatch.setattr(proposal, "call_llm", llm)

    result = proposal.run_proposal_generation(_ticket())

    assert result.status == "under_evaluation"
    for section in result.sections:
        assert section.generation_iteration == 3
        assert section.needs_human_review is False
        assert [item.overall_pass for item in section.evaluation_results] == [False, False, True]
        assert section.evaluation_results[0].compliance.passed is False
    selection = next(item for item in result.sections if item.department_id == "seleccion")
    assert any(v.startswith("SEL-15") for v in selection.evaluation_results[0].compliance.violations)


def test_always_failing_llm_stops_at_three_iterations(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = FakeLLM(lambda _n: failing_draft)
    monkeypatch.setattr(proposal, "call_llm", llm)

    result = proposal.run_proposal_generation(_ticket())

    assert proposal.MAX_GENERATION_ITERATIONS == 3
    assert result.status == "needs_human_review"
    for section in result.sections:
        assert section.needs_human_review is True
        assert section.generation_iteration == 3
        assert len(section.evaluation_results) == 3
        assert section.draft_content.endswith("Entregamos en 5 días.")
    assert len(llm.calls) == 6


def test_generator_calls_llm_per_department_and_feeds_back_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = FakeLLM(lambda n: failing_draft if n == 1 else passing_draft)
    monkeypatch.setattr(proposal, "call_llm", llm)

    proposal.run_proposal_generation(_ticket())

    for department_id in ("seleccion", "capacitacion"):
        prompts = llm.calls_for(department_id)
        assert len(prompts) == 2
        assert "Feedback de los evaluadores" not in prompts[0]
        assert "Feedback de los evaluadores" in prompts[1]
        assert "G-90" in prompts[1] and "CUR-01" in prompts[1]
        assert "Entregamos en 5 días." in prompts[1]
    assert "SEL-15" in llm.calls_for("seleccion")[1]
    assert "SEL-15" not in llm.calls_for("capacitacion")[1]


def test_department_agents_do_not_hardcode_compliance_phrases() -> None:
    for prompt in proposal.DEPARTMENT_AGENTS.values():
        text = (prompt + proposal.COMMON_INSTRUCTIONS).lower()
        assert "90 días" not in text and "24 horas" not in text and "15 días" not in text


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


def test_department_graphs_do_not_block_each_other() -> None:
    barrier = threading.Barrier(2)

    class ParallelProbeGraph:
        def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
            barrier.wait(timeout=2)
            return proposal.proposal_generation_graph.invoke(state)

    result = proposal.run_proposal_generation(_ticket(), graph=ParallelProbeGraph())

    assert {section.department_id for section in result.sections} == {"seleccion", "capacitacion"}
