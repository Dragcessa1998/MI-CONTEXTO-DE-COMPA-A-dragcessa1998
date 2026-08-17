#!/usr/bin/env python3
"""Indexa la base comercial de Nexova y muestra metadatos no sensibles."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.process.rag import setup  # noqa: E402


def main() -> int:
    print(json.dumps(setup(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
