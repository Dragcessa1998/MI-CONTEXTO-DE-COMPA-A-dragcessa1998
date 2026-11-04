"""Exportación atómica de telemetría diaria a CSV de respaldo."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .db import RelationalDatabase


CSV_FIELDS = [
    "event_id",
    "event_timestamp",
    "session_id",
    "user_id",
    "event_type",
    "schema_version",
    "request_id",
    "properties",
    "ingested_at",
]


def _query_bounds(database: RelationalDatabase, target_date: date) -> tuple[Any, Any]:
    start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    if database.kind == "sqlite":
        return start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")
    return start, end


def _property_json(value: Any) -> str:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def export_telemetry_csv(
    database_url: str,
    target_date: date,
    raw_directory: Path,
) -> tuple[Path, int, bool]:
    """Devuelve (ruta, filas, creada); nunca reemplaza un snapshot existente."""

    raw_directory.mkdir(parents=True, exist_ok=True)
    output = raw_directory / f"telemetry_{target_date.isoformat()}.csv"
    if output.exists():
        return output, 0, False

    database = RelationalDatabase(database_url)
    placeholder = database.placeholder
    start, end = _query_bounds(database, target_date)
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT event_id,event_timestamp,session_id,user_id,event_type,schema_version,request_id,properties,ingested_at "
            f"FROM telemetry_events WHERE event_timestamp >= {placeholder} AND event_timestamp < {placeholder} "
            "ORDER BY event_timestamp,event_id",
            (start, end),
        ).fetchall()

    temporary = output.with_name(f".{output.name}.tmp-{uuid4().hex}")
    try:
        with temporary.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for row in rows:
                record = {field: row[field] for field in CSV_FIELDS}
                record["properties"] = _property_json(record["properties"])
                writer.writerow(record)
        temporary.replace(output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return output, len(rows), True
