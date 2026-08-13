"""Análisis agregado y seguro del CSV histórico de incidentes de Nexova.

Este módulo es la única fuente de verdad para el script y la API. Nunca conserva
ni devuelve emails, descripciones u otros datos personales de filas concretas.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .incidents import validate_historical_row


EXPECTED_HEADERS = (
    "ticket_id",
    "date",
    "client_company",
    "category",
    "description",
    "agent_id",
    "status",
    "customer_email",
    "satisfaction_score",
)
ANALYSIS_CATEGORIES = ("TECHNICAL", "BILLING", "ACCESS", "HR_QUERY", "COMPLAINT")
ANALYSIS_STATUSES = ("OPEN", "CLOSED", "DISCARDED")
ANALYSIS_ERROR_LABELS = {
    "invalid_ticket_id": "Invalid or missing ticket_id",
    "invalid_date": "Invalid or missing date",
    "missing_client_company": "Missing client_company",
    "invalid_category": "Invalid or missing category",
    "invalid_description": "Invalid or missing description",
    "invalid_agent_id": "Invalid or missing agent_id",
    "invalid_status": "Invalid or missing status",
    "invalid_email": "Invalid or missing email",
    "closed_without_score": "Closed ticket, no score",
    "invalid_score": "Satisfaction score outside 1–5",
}


class IncidentAnalysisError(ValueError):
    """Raised when an uploaded source is not a usable Nexova incidents CSV."""


@dataclass(frozen=True)
class IncidentAnalysis:
    source_file: str
    total_records: int
    valid_records: int
    invalid_records: int
    invalid_breakdown: dict[str, int]
    category_breakdown: dict[str, int]
    status_breakdown: dict[str, int]
    closed_tickets: int
    scored_tickets: int
    average_satisfaction: float | None
    score_breakdown: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            "source_file": self.source_file,
            "total_records": self.total_records,
            "valid_records": self.valid_records,
            "invalid_records": self.invalid_records,
            "invalid_breakdown": self.invalid_breakdown,
            "category_breakdown": self.category_breakdown,
            "status_breakdown": self.status_breakdown,
            "satisfaction": {
                "closed_tickets": self.closed_tickets,
                "scored_tickets": self.scored_tickets,
                "average_score": self.average_satisfaction,
                "score_breakdown": self.score_breakdown,
            },
        }


def analyze_rows(
    rows: Iterable[Mapping[str, str | None]],
    *,
    source_file: str,
) -> IncidentAnalysis:
    total = 0
    valid = 0
    invalid = 0
    invalid_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    satisfaction_counts: Counter[int] = Counter()

    for row in rows:
        total += 1
        validation = validate_historical_row(row)
        if not validation.valid:
            invalid += 1
            invalid_counts.update(validation.errors)
            continue

        valid += 1
        category = (row.get("category") or "").strip()
        incident_status = (row.get("status") or "").strip()
        category_counts[category] += 1
        status_counts[incident_status] += 1
        score_text = (row.get("satisfaction_score") or "").strip()
        if incident_status == "CLOSED" and score_text:
            satisfaction_counts[int(score_text)] += 1

    if total == 0:
        raise IncidentAnalysisError("The CSV contains a header but no incident records.")

    scored_tickets = sum(satisfaction_counts.values())
    average = (
        round(
            sum(score * count for score, count in satisfaction_counts.items())
            / scored_tickets,
            2,
        )
        if scored_tickets
        else None
    )
    return IncidentAnalysis(
        source_file=source_file,
        total_records=total,
        valid_records=valid,
        invalid_records=invalid,
        invalid_breakdown={code: invalid_counts.get(code, 0) for code in ANALYSIS_ERROR_LABELS},
        category_breakdown={
            category: category_counts.get(category, 0)
            for category in ANALYSIS_CATEGORIES
        },
        status_breakdown={
            incident_status: status_counts.get(incident_status, 0)
            for incident_status in ANALYSIS_STATUSES
        },
        closed_tickets=status_counts.get("CLOSED", 0),
        scored_tickets=scored_tickets,
        average_satisfaction=average,
        score_breakdown={str(score): satisfaction_counts.get(score, 0) for score in range(1, 6)},
    )


def analyze_csv_text(text: str, *, source_file: str) -> IncidentAnalysis:
    if not text.strip():
        raise IncidentAnalysisError("The uploaded CSV is empty.")

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None:
        raise IncidentAnalysisError("The CSV must include a header row.")
    normalized_headers = tuple((header or "").strip() for header in reader.fieldnames)
    missing = [header for header in EXPECTED_HEADERS if header not in normalized_headers]
    if missing:
        raise IncidentAnalysisError(
            "The CSV has an incorrect format. Missing columns: " + ", ".join(missing)
        )
    return analyze_rows(reader, source_file=source_file)


def analyze_csv_bytes(content: bytes, *, source_file: str) -> IncidentAnalysis:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IncidentAnalysisError("The CSV must use UTF-8 encoding.") from exc
    return analyze_csv_text(text, source_file=source_file)


def analyze_csv_file(path: Path) -> IncidentAnalysis:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise IncidentAnalysisError(f"Could not read CSV file: {path}") from exc
    return analyze_csv_bytes(content, source_file=path.name)


def analysis_to_csv(analysis: IncidentAnalysis) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("metric", "value"))
    writer.writerow(("total_records", analysis.total_records))
    writer.writerow(("valid_records", analysis.valid_records))
    writer.writerow(("invalid_records", analysis.invalid_records))
    for code, count in analysis.invalid_breakdown.items():
        writer.writerow((f"invalid.{code}", count))
    for category, count in analysis.category_breakdown.items():
        writer.writerow((f"category.{category}", count))
    for incident_status, count in analysis.status_breakdown.items():
        writer.writerow((f"status.{incident_status}", count))
    writer.writerow(("satisfaction.closed_tickets", analysis.closed_tickets))
    writer.writerow(("satisfaction.scored_tickets", analysis.scored_tickets))
    writer.writerow(("satisfaction.average_score", analysis.average_satisfaction or ""))
    for score, count in analysis.score_breakdown.items():
        writer.writerow((f"satisfaction.score.{score}", count))
    return output.getvalue()


def render_console_report(analysis: IncidentAnalysis) -> str:
    valid_total = analysis.valid_records

    def percentage(count: int) -> str:
        return f"{(count / valid_total * 100) if valid_total else 0:.1f}%"

    lines = [
        "=" * 60,
        "  NEXOVA — SUPPORT TICKET ANALYSIS",
        f"  Source file: {analysis.source_file}",
        "=" * 60,
        "",
        f"TOTAL RECORDS IN FILE .......... {analysis.total_records}",
        f"  ├─ Valid records ................ {analysis.valid_records}",
        f"  └─ Invalid / incomplete .......... {analysis.invalid_records}",
        "",
        "INVALID RECORDS BREAKDOWN",
    ]
    for code, count in analysis.invalid_breakdown.items():
        if count:
            lines.append(f"  ├─ {ANALYSIS_ERROR_LABELS[code]:<34} {count}")

    lines.extend(("", "BREAKDOWN BY CATEGORY (valid records)"))
    for category, count in analysis.category_breakdown.items():
        lines.append(f"  ├─ {category:<28} {count:>3}  ({percentage(count)})")

    lines.extend(("", "BREAKDOWN BY STATUS (valid records)"))
    for incident_status, count in analysis.status_breakdown.items():
        lines.append(f"  ├─ {incident_status:<28} {count:>3}  ({percentage(count)})")

    average = (
        f"{analysis.average_satisfaction:.2f} / 5.00"
        if analysis.average_satisfaction is not None
        else "Not available"
    )
    lines.extend(
        (
            "",
            "SATISFACTION INDEX (closed tickets)",
            f"  Scored tickets: {analysis.scored_tickets} of {analysis.closed_tickets}",
            f"  Average score: {average}",
        )
    )
    score_labels = {
        "1": "Very dissatisfied",
        "2": "Dissatisfied",
        "3": "Neutral",
        "4": "Satisfied",
        "5": "Very satisfied",
    }
    for score, count in analysis.score_breakdown.items():
        lines.append(f"  ├─ Score {score} ({score_labels[score]}) ... {count}")
    lines.extend(("", "=" * 60))
    return "\n".join(lines)
