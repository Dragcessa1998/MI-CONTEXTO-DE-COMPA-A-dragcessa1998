from __future__ import annotations

from pathlib import Path
from shutil import copy2

import pytest

from data.pipelines.rfp_intake import run_rfp_intake
from data.pipelines.rfp_intake.agents import department_worker, extract_metadata


SAMPLES = Path(
    "/Users/franchescostabile/Desktop/tareas pendientes/course-syllabus/content/contexts/09-agentic-workflows/rfp-requests/nexova"
)


def _run_sample(tmp_path: Path, name: str):
    source = SAMPLES / name
    if not source.is_file():
        pytest.skip("Los PDF oficiales de Nexova no están disponibles en este entorno")
    target = tmp_path / name
    copy2(source, target)
    return run_rfp_intake(target)


def test_formal_rfp_routes_only_selection_and_training(tmp_path: Path) -> None:
    result = _run_sample(tmp_path, "CONTEXT-nexova-request-1.pdf")

    assert result.classification.is_rfp is True
    assert result.metadata is not None
    assert result.metadata.client_name == "Vantex Retail Group, S.A."
    assert result.metadata.client_hq == "España"
    assert result.metadata.currency == "EUR"
    assert result.metadata.deadline == "2026-08-18"
    assert result.metadata.volumes == {"roles": 5, "participants": 40}
    assert result.metadata.departments_needed == ["seleccion", "capacitacion"]
    assert {section.contact for section in result.sections} == {"Javier Almeida", "Elena Vargas"}
    assert Path(result.markdown_path).is_file()


def test_informal_rfp_is_accepted_and_routes_to_support(tmp_path: Path) -> None:
    result = _run_sample(tmp_path, "CONTEXT-nexova-request-2.pdf")

    assert result.classification.is_rfp is True
    assert result.metadata is not None
    assert result.metadata.client_name == "NubeSoft"
    assert result.metadata.client_hq == "Miami"
    assert result.metadata.currency == "USD"
    assert result.metadata.volumes == {"support_agents": 12}
    assert result.metadata.departments_needed == ["soporte"]
    assert [section.contact for section in result.sections] == ["Roberto Díaz"]
    assert "12 support agents" in " ".join(result.sections[0].key_aspects)


def test_vendor_pitch_is_rejected_before_orchestration(tmp_path: Path) -> None:
    result = _run_sample(tmp_path, "CONTEXT-nexova-request-3.pdf")

    assert result.classification.is_rfp is False
    assert "pitch de proveedor" in result.classification.reason
    assert result.metadata is None
    assert result.sections == []


def test_worker_keeps_missing_values_as_open_questions() -> None:
    markdown = "# RFP\n\nCliente en Madrid solicita formación en liderazgo."
    metadata = extract_metadata(markdown)
    section = department_worker("capacitacion", metadata, markdown)

    assert metadata.budget_range is None
    assert "Confirmar presupuesto" in section.open_questions[0]
    assert any("volumen exacto" in question for question in section.open_questions)
    assert not any("40" in aspect for aspect in section.key_aspects)
