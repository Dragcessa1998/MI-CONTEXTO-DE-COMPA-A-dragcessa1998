#!/usr/bin/env python3
"""Analyze a Nexova incident CSV without exposing row-level customer data."""

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "packages" / "shared"))

from nexova_shared.incident_analysis import (  # noqa: E402
    IncidentAnalysisError,
    analysis_to_csv,
    analyze_csv_file,
    render_console_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="Path to incidents CSV")
    args = parser.parse_args()

    try:
        analysis = analyze_csv_file(args.csv)
    except IncidentAnalysisError as exc:
        parser.error(str(exc))

    print(render_console_report(analysis))
    choice = input("Export results to CSV? [y / n]: ").strip().lower()
    if choice in {"y", "yes"}:
        output_path = Path.cwd() / "results.csv"
        output_path.write_text(analysis_to_csv(analysis), encoding="utf-8", newline="")
        print(f"Results exported to {output_path}")
    else:
        print("Results were not exported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
