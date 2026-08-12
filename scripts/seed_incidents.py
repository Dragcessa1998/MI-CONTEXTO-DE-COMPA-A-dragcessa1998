#!/usr/bin/env python3
"""Carga idempotente de incidentes históricos Nexova desde el CSV validado."""

import argparse
import csv
import sys
from collections import Counter
from json import JSONDecodeError
from pathlib import Path

from tinydb.table import Document


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "packages" / "shared"))
sys.path.insert(0, str(REPO_ROOT / "services" / "api"))

from database import incidents_table  # noqa: E402
from nexova_shared.incidents import (  # noqa: E402
    ERROR_LABELS,
    transform_historical_row,
    validate_historical_row,
)


DEFAULT_CSV = REPO_ROOT / "data" / "incidents-nexova.csv"


def seed(csv_path: Path) -> dict[str, object]:
    table = incidents_table()
    total = inserted = skipped = invalid = 0
    errors: Counter[str] = Counter()

    with csv_path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        required_headers = {
            "ticket_id", "date", "client_company", "category", "description",
            "agent_id", "status", "customer_email", "satisfaction_score",
        }
        if reader.fieldnames is None or not required_headers.issubset(reader.fieldnames):
            raise csv.Error("cabeceras obligatorias ausentes")
        for row in reader:
            total += 1
            validation = validate_historical_row(row)
            if not validation.valid:
                invalid += 1
                errors.update(validation.errors)
                continue

            incident = transform_historical_row(row)
            # El número del ticket se usa como doc_id determinista, pero no se
            # guarda como campo del modelo (regla explícita del CONTEXT).
            source_doc_id = int((row.get("ticket_id") or "").split("-")[-1])
            if table.contains(doc_id=source_doc_id):
                skipped += 1
                continue
            incident["id"] = source_doc_id
            table.insert(Document(incident, doc_id=source_doc_id))
            inserted += 1

    return {
        "total": total,
        "valid": total - invalid,
        "inserted": inserted,
        "skipped": skipped,
        "invalid": invalid,
        "errors": errors,
        "stored": len(table),
    }


def print_report(result: dict[str, object], csv_path: Path) -> None:
    print("NEXOVA — SEED DE INCIDENTES HISTÓRICOS")
    print(f"Fuente: {csv_path.name}")
    print(f"Filas leídas: {result['total']}")
    print(f"Filas válidas: {result['valid']}")
    print(f"Insertadas: {result['inserted']}")
    print(f"Omitidas por duplicado: {result['skipped']}")
    print(f"Inválidas: {result['invalid']}")
    errors = result["errors"]
    if isinstance(errors, Counter):
        for code, count in sorted(errors.items()):
            print(f"  - {ERROR_LABELS.get(code, code)}: {count}")
    print(f"Total almacenado: {result['stored']}")
    print("No se imprimieron emails ni otros datos personales.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="?", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args(argv)
    if not args.csv.is_file():
        print(f"No se encontró el archivo de entrada: {args.csv.name}", file=sys.stderr)
        return 1
    try:
        result = seed(args.csv)
    except (OSError, UnicodeError, csv.Error, JSONDecodeError, ValueError):
        print(
            "No se pudo procesar el CSV o guardar los incidentes. "
            "Comprueba el formato, los permisos y la base local.",
            file=sys.stderr,
        )
        return 1
    print_report(result, args.csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
