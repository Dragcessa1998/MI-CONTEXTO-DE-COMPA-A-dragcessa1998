"""La evidencia de hardening debe poder verificarse sin tocar el host local."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = ROOT / "scripts/security/validate_hardening.py"


def test_declared_server_hardening_is_closed_by_default() -> None:
    spec = importlib.util.spec_from_file_location("validate_hardening", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.validate() == []
