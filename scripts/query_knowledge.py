#!/usr/bin/env python3
"""Consulta manual del RAG comercial de Nexova."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.pipelines.rag import query  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    args = parser.parse_args()
    print(query(args.question))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
