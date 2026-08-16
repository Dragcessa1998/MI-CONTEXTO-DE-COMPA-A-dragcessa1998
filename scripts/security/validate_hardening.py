#!/usr/bin/env python3
"""Valida estáticamente el baseline sin modificar el host de desarrollo."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def validate() -> list[str]:
    findings: list[str] = []
    ssh = (ROOT / "infra/security/sshd_config.d/99-nexova-hardening.conf").read_text()
    for directive in (
        "PermitRootLogin no",
        "PasswordAuthentication no",
        "AuthenticationMethods publickey",
        "AllowUsers nexova-deploy",
    ):
        if directive not in ssh:
            findings.append(f"SSH: falta {directive}")

    nft = (ROOT / "infra/security/nftables.conf").read_text()
    if "policy drop" not in nft:
        findings.append("firewall: input/forward no usan deny by default")
    ports = re.search(r"tcp dport \{\s*([^}]+)\}", nft)
    normalized_ports = {item.strip() for item in ports.group(1).split(",")} if ports else set()
    if normalized_ports != {"22", "443"}:
        findings.append(f"firewall: puertos públicos inesperados {sorted(normalized_ports)}")

    docker_users = {
        "services/Dockerfile": "USER nexova",
        "uis/Dockerfile": "USER node",
        "services/talent-api/Dockerfile": "USER node",
    }
    for relative, instruction in docker_users.items():
        if instruction not in (ROOT / relative).read_text():
            findings.append(f"contenedor: {relative} no contiene {instruction}")

    compose = (ROOT / "docker-compose.yml").read_text()
    published = re.findall(r'- "([^"\n]+):(?:3000|3001|4000|6333|8000)"', compose)
    if not published or any(not item.startswith("127.0.0.1:") for item in published):
        findings.append("compose: algún servicio interno no está enlazado a loopback")
    return findings


def main() -> int:
    findings = validate()
    if findings:
        print("Baseline inválido:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("OK: root SSH deshabilitado, sólo 22/443 y contenedores non-root")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
