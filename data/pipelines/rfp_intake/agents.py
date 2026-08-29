"""Clasificador, orquestador, workers y synthesizer específicos de Nexova."""

from __future__ import annotations

import re
from typing import Any

from data.pipelines.rfp_intake.document import calculate_readability
from data.pipelines.rfp_intake.models import (
    Classification,
    DepartmentId,
    DepartmentSection,
    RfpMetadata,
)


DEPARTMENTS: dict[DepartmentId, tuple[str, str]] = {
    "seleccion": ("Talent Selection Operations", "Javier Almeida"),
    "capacitacion": ("Corporate Training", "Elena Vargas"),
    "soporte": ("Customer Support (outsourcing)", "Roberto Díaz"),
}
TERMS: dict[DepartmentId, tuple[str, ...]] = {
    "seleccion": ("búsqueda ejecutiva", "headhunting", "mandos medios", "posiciones", "roles"),
    "capacitacion": ("formación", "training", "liderazgo", "participantes", "capacitación"),
    "soporte": ("support", "soporte", "agentes", "24/7", "sla", "response"),
}
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def classify_document(markdown: str) -> Classification:
    lower = " ".join(markdown.lower().split())
    vendor_pitch = any(
        phrase in lower
        for phrase in (
            "upgrade your ats",
            "introduce hirestream",
            "15-minute demo",
            "applicant tracking system",
        )
    )
    requests_proposal = any(
        phrase in lower
        for phrase in ("request for proposal", "solicitud de propuesta", "put together a proposal")
    )
    requested_service = any(term in lower for terms in TERMS.values() for term in terms)
    if vendor_pitch:
        return Classification(is_rfp=False, reason="Es un pitch de proveedor dirigido a Nexova, no una solicitud de cliente.")
    if requests_proposal and requested_service:
        return Classification(is_rfp=True, reason="Solicita una propuesta para servicios que presta Nexova.")
    return Classification(is_rfp=False, reason="No contiene una solicitud de propuesta con alcance de servicios Nexova.")


def _sentences(markdown: str) -> list[str]:
    compact = " ".join(line.strip() for line in markdown.splitlines() if line.strip() and not line.startswith("#"))
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+|\n+", compact) if item.strip()]


def _deadline(text: str) -> str | None:
    matches = re.findall(
        r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?(?:,)?\s+(202\d)\b",
        text,
        flags=re.IGNORECASE,
    )
    if matches:
        month, day, year = matches[-1]
        return f"{int(year):04d}-{MONTHS[month.lower()]:02d}-{int(day):02d}"
    partial = re.findall(
        r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?\b",
        text,
        flags=re.IGNORECASE,
    )
    if partial:
        month, day = partial[-1]
        return f"{month} {int(day)} (año no indicado)"
    return None


def extract_metadata(markdown: str) -> RfpMetadata:
    lower = markdown.lower()
    organization = re.search(r"Issuing Organization:\s*([^\n]+)", markdown, re.IGNORECASE)
    if organization:
        client_name = organization.group(1).strip()
    elif "nubesoft" in lower:
        client_name = "NubeSoft"
    elif "hirestream" in lower:
        client_name = "HireStream"
    else:
        client_name = "Cliente por confirmar"

    if "madrid" in lower or "españa" in lower:
        client_hq, currency = "España", "EUR"
    elif "miami" in lower or "usa" in lower:
        client_hq, currency = "Miami", "USD"
    else:
        client_hq, currency = "desconocida", "por_confirmar"

    departments: list[DepartmentId] = []
    services: list[str] = []
    if any(term in lower for term in TERMS["seleccion"]):
        departments.append("seleccion")
        services.append("búsqueda ejecutiva")
    if any(term in lower for term in TERMS["capacitacion"]):
        departments.append("capacitacion")
        services.append("formación corporativa")
    if any(term in lower for term in TERMS["soporte"]):
        departments.append("soporte")
        services.append("soporte externalizado")

    volumes: dict[str, int] = {}
    patterns = {
        "roles": r"(\d+)\s+(?:posiciones|roles)",
        "participants": r"(\d+)\s+participantes",
        "support_agents": r"(\d+)\s+support agents",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, lower)
        if match:
            volumes[key] = int(match.group(1))

    relevant = [
        sentence for sentence in _sentences(markdown)
        if any(term in sentence.lower() for terms in TERMS.values() for term in terms)
    ]
    money = re.search(r"(?:EUR|USD|€|\$)\s*[\d.,]+(?:\s*(?:-|a)\s*(?:EUR|USD|€|\$)?\s*[\d.,]+)?", markdown, re.IGNORECASE)
    return RfpMetadata(
        client_name=client_name,
        client_hq=client_hq,
        currency=currency,
        services_requested=services,
        scope=" ".join(relevant[:4])[:2000] or "Alcance por confirmar",
        volumes=volumes,
        deadline=_deadline(markdown),
        budget_range=money.group(0) if money else None,
        departments_needed=departments,
        readability=calculate_readability(markdown),
    )


def orchestrate(metadata: RfpMetadata) -> list[DepartmentId]:
    """Activa sólo los departamentos derivados de los servicios solicitados."""
    return list(metadata.departments_needed)


def select_department_context(department_id: DepartmentId, markdown: str) -> str:
    """Reduce el documento a extractos del workstream antes de entregarlo al worker."""
    terms = TERMS[department_id]
    excerpts = [
        sentence
        for sentence in _sentences(markdown)
        if any(term in sentence.lower() for term in terms)
    ]
    return "\n".join(excerpts)


def department_worker(
    department_id: DepartmentId,
    metadata: RfpMetadata,
    department_context: str,
) -> DepartmentSection:
    terms = TERMS[department_id]
    excerpts = [
        sentence
        for sentence in _sentences(department_context)
        if any(term in sentence.lower() for term in terms)
    ]
    key_aspects = excerpts[:8]
    open_questions: list[str] = []
    if metadata.budget_range is None:
        open_questions.append("Confirmar presupuesto o rango económico disponible.")
    if metadata.deadline is None:
        open_questions.append("Confirmar fecha límite de la propuesta.")
    volume_key = {"seleccion": "roles", "capacitacion": "participants", "soporte": "support_agents"}[department_id]
    if volume_key not in metadata.volumes:
        open_questions.append("Confirmar el volumen exacto requerido para este workstream.")
    if department_id == "soporte" and not any("24/7" in item for item in key_aspects):
        open_questions.append("Confirmar cobertura de turnos y horario requerido.")
    department_name, contact = DEPARTMENTS[department_id]
    return DepartmentSection(
        department_id=department_id,
        department_name=department_name,
        contact=contact,
        key_aspects=key_aspects or ["El documento menciona el servicio, pero requiere aclarar su alcance."],
        open_questions=open_questions,
        relevant_excerpts=excerpts[:8],
    )


def synthesize(metadata: RfpMetadata, sections: list[DepartmentSection]) -> str:
    assignments = "; ".join(
        f"{section.contact} ({section.department_name}): revisar {len(section.key_aspects)} aspectos clave"
        for section in sections
    )
    return (
        f"RFP de {metadata.client_name} ({metadata.client_hq}, {metadata.currency}). "
        f"Workstreams: {assignments}. Las preguntas abiertas deben resolverse antes de generar precios o compromisos."
    )
