#!/usr/bin/env python3
"""Mide Recall@3 sobre las preguntas versionadas del CONTEXT de Nexova."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.pipelines.rag import DEFAULT_MIN_SCORE, retrieve  # noqa: E402


QUERIES_PATH = ROOT / "data" / "eval" / "test-queries.json"
RESULTS_PATH = ROOT / "data" / "eval" / "recall-results.json"


def evaluate() -> dict[str, Any]:
    test_queries = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for item in test_queries:
        hits = retrieve(item["question"], k=3, min_score=DEFAULT_MIN_SCORE)
        sources = [hit["source_document"] for hit in hits]
        rows.append(
            {
                "id": item["id"],
                "expected_source_document": item["expected_source_document"],
                "retrieved_source_documents": sources,
                "hit": item["expected_source_document"] in sources,
            }
        )
    hits = sum(row["hit"] for row in rows)
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "metric": "Recall@3",
        "minimum_score": DEFAULT_MIN_SCORE,
        "hits": hits,
        "total": len(rows),
        "recall_at_3": round(hits / len(rows), 4),
        "passed": hits / len(rows) >= 0.8,
        "results": rows,
    }


def main() -> int:
    result = evaluate()
    RESULTS_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
