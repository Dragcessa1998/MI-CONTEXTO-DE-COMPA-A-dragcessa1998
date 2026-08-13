import csv
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nexova_shared.incident_analysis import (
    IncidentAnalysisError,
    analysis_to_csv,
    analyze_csv_file,
    analyze_csv_text,
    render_console_report,
)
from routes.incidents import reset_last_analysis


REPO_ROOT = Path(__file__).resolve().parents[3]
CSV_PATH = REPO_ROOT / "data" / "incidents-nexova.csv"


@pytest.fixture(autouse=True)
def isolated_analysis_state():
    reset_last_analysis()
    yield
    reset_last_analysis()


def test_shared_analysis_matches_nexova_context_exactly():
    analysis = analyze_csv_file(CSV_PATH)

    assert analysis.total_records == 100
    assert analysis.valid_records == 96
    assert analysis.invalid_records == 4
    assert {key: value for key, value in analysis.invalid_breakdown.items() if value} == {
        "missing_client_company": 1,
        "invalid_category": 1,
        "invalid_email": 1,
        "closed_without_score": 1,
    }
    assert analysis.category_breakdown == {
        "TECHNICAL": 28,
        "BILLING": 18,
        "ACCESS": 21,
        "HR_QUERY": 17,
        "COMPLAINT": 12,
    }
    assert analysis.status_breakdown == {"OPEN": 27, "CLOSED": 56, "DISCARDED": 13}
    assert analysis.closed_tickets == analysis.scored_tickets == 56
    assert analysis.average_satisfaction == 3.84
    assert analysis.score_breakdown == {"1": 2, "2": 5, "3": 10, "4": 22, "5": 17}


def test_outputs_are_aggregated_and_never_expose_customer_email():
    analysis = analyze_csv_file(CSV_PATH)
    source_text = CSV_PATH.read_text(encoding="utf-8")
    first_email = next(csv.DictReader(source_text.splitlines()))["customer_email"]

    outputs = (
        repr(analysis.as_dict()),
        render_console_report(analysis),
        analysis_to_csv(analysis),
    )
    assert all(first_email not in output for output in outputs)
    assert all("@" not in output for output in outputs)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "empty"),
        ("ticket_id,status\nNXV-000001,OPEN\n", "Missing columns"),
        (
            ",".join(
                (
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
            )
            + "\n",
            "no incident records",
        ),
    ],
)
def test_shared_analysis_rejects_empty_or_incorrect_csv(text: str, message: str):
    with pytest.raises(IncidentAnalysisError, match=message):
        analyze_csv_text(text, source_file="bad.csv")


def test_cli_accepts_path_prints_summary_and_exports_csv(tmp_path: Path):
    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "analyze.py"), str(CSV_PATH)],
        input="y\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "TOTAL RECORDS IN FILE .......... 100" in completed.stdout
    assert "Valid records ................ 96" in completed.stdout
    assert "Average score: 3.84 / 5.00" in completed.stdout
    exported = tmp_path / "results.csv"
    assert exported.is_file()
    rows = list(csv.DictReader(exported.read_text(encoding="utf-8").splitlines()))
    assert rows[0] == {"metric": "total_records", "value": "100"}
    assert {"metric": "satisfaction.average_score", "value": "3.84"} in rows


def test_api_analyzes_csv_and_exports_last_result(client: TestClient):
    response = client.post(
        "/api/incidents/analyze",
        files={"file": ("incidents-nexova.csv", CSV_PATH.read_bytes(), "text/csv")},
    )

    assert response.status_code == 200
    summary = response.json()
    assert summary["total_records"] == 100
    assert summary["valid_records"] == 96
    assert summary["invalid_records"] == 4
    assert summary["category_breakdown"]["TECHNICAL"] == 28
    assert summary["satisfaction"]["average_score"] == 3.84
    assert "@" not in response.text

    export = client.get("/api/incidents/results/export")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert export.headers["content-disposition"] == 'attachment; filename="results.csv"'
    assert "total_records,100" in export.text
    assert "satisfaction.average_score,3.84" in export.text
    assert "@" not in export.text


def test_api_rejects_bad_inputs_and_export_without_analysis(client: TestClient):
    assert client.get("/api/incidents/results/export").status_code == 404

    wrong_extension = client.post(
        "/api/incidents/analyze",
        files={"file": ("incidents.txt", CSV_PATH.read_bytes(), "text/plain")},
    )
    empty = client.post(
        "/api/incidents/analyze",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    malformed = client.post(
        "/api/incidents/analyze",
        files={"file": ("bad.csv", b"name,status\nexample,OPEN\n", "text/csv")},
    )
    invalid_encoding = client.post(
        "/api/incidents/analyze",
        files={"file": ("bad.csv", b"\xff\xfe\x00", "text/csv")},
    )

    assert wrong_extension.status_code == 400
    assert empty.status_code == 400
    assert malformed.status_code == 400
    assert invalid_encoding.status_code == 400
    assert "Missing columns" in malformed.json()["detail"]
    assert "UTF-8" in invalid_encoding.json()["detail"]


def test_analysis_routes_require_authentication(anonymous_client: TestClient):
    upload = anonymous_client.post(
        "/api/incidents/analyze",
        files={"file": ("incidents.csv", CSV_PATH.read_bytes(), "text/csv")},
    )
    export = anonymous_client.get("/api/incidents/results/export")

    assert upload.status_code == 401
    assert export.status_code == 401
