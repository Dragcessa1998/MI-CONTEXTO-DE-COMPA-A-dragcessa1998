"""Agregado semanal mínimo que el orquestador nocturno ejecuta como subprocess."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from services.job_runner.db import RelationalDatabase


PIPELINE_NAME = "weekly_office_program_performance"
EVENT_TYPES = {
    "inbound_order_created",
    "outbound_order_created",
    "stock_threshold_triggered",
    "kit_cost_variance_detected",
}
CURRENCY_BY_OFFICE = {"valencia": "EUR", "miami": "USD"}


@dataclass
class Aggregate:
    office: str
    programme_id: str
    currency: str
    total_material_cost: Decimal = Decimal("0")
    kits_delivered_count: int = 0
    shortage_events_count: int = 0
    cost_variance_events_count: int = 0


def _safe_error(error: BaseException) -> str:
    message = " ".join(str(error).split())[:500]
    return message or error.__class__.__name__


def _week_bounds(target_date: date) -> tuple[date, datetime, datetime]:
    week_start = target_date - timedelta(days=target_date.weekday())
    start = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
    return week_start, start, start + timedelta(days=7)


def _db_value(database: RelationalDatabase, value: date | datetime | Decimal | str | int) -> Any:
    if database.kind == "sqlite":
        if isinstance(value, (date, datetime)):
            return value.isoformat().replace("+00:00", "Z")
        if isinstance(value, Decimal):
            return str(value)
    return value


def _properties(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("properties must be a JSON object")


def _initialize_sqlite(database: RelationalDatabase) -> None:
    if database.kind != "sqlite":
        return
    with database.connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS reporting_weekly_office_program_performance (
              id TEXT PRIMARY KEY,
              office TEXT NOT NULL,
              programme_id TEXT NOT NULL,
              week_start TEXT NOT NULL,
              total_material_cost TEXT NOT NULL DEFAULT '0',
              kits_delivered_count INTEGER NOT NULL DEFAULT 0,
              shortage_events_count INTEGER NOT NULL DEFAULT 0,
              cost_variance_events_count INTEGER NOT NULL DEFAULT 0,
              currency TEXT NOT NULL,
              computed_at TEXT NOT NULL,
              UNIQUE (office, programme_id, week_start)
            );
            CREATE TABLE IF NOT EXISTS reporting_pipeline_runs (
              id TEXT PRIMARY KEY,
              pipeline_name TEXT NOT NULL,
              target_week TEXT NOT NULL,
              status TEXT NOT NULL CHECK (status IN ('processing','completed','failed')),
              rows_extracted INTEGER NOT NULL DEFAULT 0,
              rows_valid INTEGER NOT NULL DEFAULT 0,
              rows_quarantined INTEGER NOT NULL DEFAULT 0,
              duplicates_count INTEGER NOT NULL DEFAULT 0,
              started_at TEXT NOT NULL,
              finished_at TEXT,
              error_message TEXT
            );
            """
        )


def _table_names(database: RelationalDatabase) -> tuple[str, str]:
    if database.kind == "sqlite":
        return "reporting_weekly_office_program_performance", "reporting_pipeline_runs"
    return "reporting.weekly_office_program_performance", "reporting.pipeline_runs"


def run_pipeline(database_url: str, target_date: date) -> str:
    database = RelationalDatabase(database_url)
    _initialize_sqlite(database)
    aggregate_table, run_table = _table_names(database)
    placeholder = database.placeholder
    week_start, start, end = _week_bounds(target_date)
    run_id = str(uuid4())
    started_at = datetime.now(timezone.utc)

    with database.connect() as connection:
        database.begin_write(connection)
        connection.execute(
            f"INSERT INTO {run_table} (id,pipeline_name,target_week,status,started_at) VALUES ({','.join([placeholder] * 5)})",
            (
                run_id,
                PIPELINE_NAME,
                _db_value(database, week_start),
                "processing",
                _db_value(database, started_at),
            ),
        )
        connection.commit()

    try:
        query_start = _db_value(database, start)
        query_end = _db_value(database, end)
        with database.connect() as connection:
            rows = connection.execute(
                "SELECT event_id,event_timestamp,event_type,properties,ingested_at FROM telemetry_events "
                f"WHERE event_timestamp >= {placeholder} AND event_timestamp < {placeholder} "
                f"AND event_type IN ({','.join([placeholder] * len(EVENT_TYPES))}) "
                "ORDER BY event_id,ingested_at",
                (query_start, query_end, *sorted(EVENT_TYPES)),
            ).fetchall()

        latest_by_event: dict[str, Any] = {}
        duplicates = 0
        for row in rows:
            event_id = str(row["event_id"])
            if event_id in latest_by_event:
                duplicates += 1
            latest_by_event[event_id] = row

        aggregates: dict[tuple[str, str], Aggregate] = {}
        quarantined = 0
        for row in latest_by_event.values():
            try:
                props = _properties(row["properties"])
                office = str(props["office"])
                programme_id = str(props["programme_id"]).strip()
                currency = str(props["currency"])
                if office not in CURRENCY_BY_OFFICE or currency != CURRENCY_BY_OFFICE[office]:
                    raise ValueError("office/currency mismatch")
                if not programme_id:
                    raise ValueError("empty programme_id")
                key = (office, programme_id)
                aggregate = aggregates.setdefault(
                    key,
                    Aggregate(office=office, programme_id=programme_id, currency=currency),
                )
                event_type = str(row["event_type"])
                if event_type == "inbound_order_created":
                    quantity = int(props["quantity"])
                    unit_cost = Decimal(str(props["unit_cost"]))
                    if quantity <= 0 or unit_cost < 0 or not unit_cost.is_finite():
                        raise ValueError("invalid inbound cost or quantity")
                    aggregate.total_material_cost += quantity * unit_cost
                elif event_type == "outbound_order_created":
                    aggregate.kits_delivered_count += 1
                elif event_type == "stock_threshold_triggered":
                    aggregate.shortage_events_count += 1
                elif event_type == "kit_cost_variance_detected":
                    aggregate.cost_variance_events_count += 1
                else:
                    raise ValueError("event type outside pipeline contract")
            except (KeyError, TypeError, ValueError, InvalidOperation, json.JSONDecodeError):
                quarantined += 1

        if latest_by_event and quarantined / len(latest_by_event) > 0.01:
            raise RuntimeError(
                f"quality gate failed: {quarantined}/{len(latest_by_event)} rows quarantined"
            )

        finished_at = datetime.now(timezone.utc)
        with database.connect() as connection:
            database.begin_write(connection)
            for aggregate in aggregates.values():
                values = (
                    str(uuid4()),
                    aggregate.office,
                    aggregate.programme_id,
                    _db_value(database, week_start),
                    _db_value(database, aggregate.total_material_cost),
                    aggregate.kits_delivered_count,
                    aggregate.shortage_events_count,
                    aggregate.cost_variance_events_count,
                    aggregate.currency,
                    _db_value(database, finished_at),
                )
                connection.execute(
                    f"INSERT INTO {aggregate_table} (id,office,programme_id,week_start,total_material_cost,kits_delivered_count,shortage_events_count,cost_variance_events_count,currency,computed_at) "
                    f"VALUES ({','.join([placeholder] * 10)}) "
                    "ON CONFLICT (office,programme_id,week_start) DO UPDATE SET "
                    "total_material_cost=excluded.total_material_cost,kits_delivered_count=excluded.kits_delivered_count,"
                    "shortage_events_count=excluded.shortage_events_count,cost_variance_events_count=excluded.cost_variance_events_count,"
                    "currency=excluded.currency,computed_at=excluded.computed_at",
                    values,
                )
            connection.execute(
                f"UPDATE {run_table} SET status='completed',rows_extracted={placeholder},rows_valid={placeholder},rows_quarantined={placeholder},duplicates_count={placeholder},finished_at={placeholder} WHERE id={placeholder} AND status='processing'",
                (
                    len(rows),
                    len(latest_by_event) - quarantined,
                    quarantined,
                    duplicates,
                    _db_value(database, finished_at),
                    run_id,
                ),
            )
            connection.commit()
        return run_id
    except BaseException as error:
        finished_at = datetime.now(timezone.utc)
        with database.connect() as connection:
            database.begin_write(connection)
            connection.execute(
                f"UPDATE {run_table} SET status='failed',finished_at={placeholder},error_message={placeholder} WHERE id={placeholder} AND status='processing'",
                (_db_value(database, finished_at), _safe_error(error), run_id),
            )
            connection.commit()
        raise


def parse_target_date(raw: str | None) -> date:
    if raw is None:
        return datetime.now(timezone.utc).date() - timedelta(days=1)
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("TARGET_DATE debe usar YYYY-MM-DD") from exc
    if parsed.isoformat() != raw:
        raise ValueError("TARGET_DATE debe usar YYYY-MM-DD")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-date", default=os.getenv("TARGET_DATE"))
    args = parser.parse_args()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        parser.error("DATABASE_URL es obligatorio")
    target = parse_target_date(args.target_date)
    run_id = run_pipeline(database_url, target)
    print(f"pipeline_run_id={run_id} target_week={_week_bounds(target)[0].isoformat()} status=completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
