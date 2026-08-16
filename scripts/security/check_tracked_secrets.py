#!/usr/bin/env python3
"""Falla si un archivo rastreado contiene una credencial con formato real."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "openai-key": re.compile(r"\bsk-(?!example|test)[A-Za-z0-9_-]{20,}\b"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode() for item in result.stdout.split(b"\0") if item]


def scan() -> list[str]:
    findings: list[str] = []
    for path in tracked_files():
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        relative = path.relative_to(ROOT)
        for rule_id, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{relative}: {rule_id}")
    return findings


def main() -> int:
    findings = scan()
    if findings:
        print("Credenciales potenciales detectadas:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("OK: 0 credenciales con formato real en archivos rastreados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
