"""Reprocesa un PDF RFP local mediante el mismo grafo que usa la API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data.pipelines.rfp_intake import run_rfp_intake


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    result = run_rfp_intake(args.pdf.resolve())
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
