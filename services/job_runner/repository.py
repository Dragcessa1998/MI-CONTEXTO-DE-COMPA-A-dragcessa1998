"""Persistencia y máquina de estados pending → processing → completed|failed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from .db import RelationalDatabase


FINAL_STATUSES = {"completed", "failed"}
VALID_STATUSES = {"pending", "processing", *FINAL_STATUSES}


@dataclass(frozen=True)
class JobRun:
    id: str
    job_name: str
    target_date: date
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    created_at: datetime


class ClaimOutcome(str, Enum):
    ACQUIRED = "acquired"
    ALREADY_PROCESSING = "already_processing"
    ALREADY_COMPLETED = "already_completed"


@dataclass(frozen=True)
class ClaimResult:
    outcome: ClaimOutcome
    run_id: str | None = None


class JobRunRepository:
    JOB_TABLE = "job_runs"

    def __init__(self, database_url: str):
        self.db = RelationalDatabase(database_url)
        if self.db.kind == "sqlite":
            self._initialize_sqlite()
        else:
            self.JOB_TABLE = "orchestration.job_runs"

    def _initialize_sqlite(self) -> None:
        with self.db.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS job_runs (
                  id TEXT PRIMARY KEY,
                  job_name TEXT NOT NULL,
                  target_date TEXT NOT NULL,
                  status TEXT NOT NULL CHECK (status IN ('pending','processing','completed','failed')),
                  started_at TEXT,
                  finished_at TEXT,
                  error_message TEXT,
                  created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_job_runs_name_date
                  ON job_runs (job_name, target_date);
                CREATE UNIQUE INDEX IF NOT EXISTS uq_job_runs_one_processing
                  ON job_runs (job_name) WHERE status = 'processing';
                CREATE UNIQUE INDEX IF NOT EXISTS uq_job_runs_completed_date
                  ON job_runs (job_name, target_date) WHERE status = 'completed';
                """
            )

    def _value(self, value: date | datetime | str | None) -> Any:
        if self.db.kind == "sqlite" and isinstance(value, (date, datetime)):
            return value.isoformat()
        return value

    def _fetchone(self, connection: Any, sql: str, params: tuple[Any, ...]) -> Any:
        return connection.execute(sql, params).fetchone()

    def has_processing_lock(self, job_name: str) -> bool:
        placeholder = self.db.placeholder
        with self.db.connect() as connection:
            row = self._fetchone(
                connection,
                f"SELECT 1 FROM {self.JOB_TABLE} WHERE job_name={placeholder} AND status='processing' LIMIT 1",
                (job_name,),
            )
            return row is not None

    def has_completed_for_date(self, job_name: str, target_date: date) -> bool:
        placeholder = self.db.placeholder
        with self.db.connect() as connection:
            row = self._fetchone(
                connection,
                f"SELECT 1 FROM {self.JOB_TABLE} WHERE job_name={placeholder} AND target_date={placeholder} AND status='completed' LIMIT 1",
                (job_name, self._value(target_date)),
            )
            return row is not None

    def create_run(self, job_name: str, target_date: date) -> str:
        """Crea un pending explícito; claim() lo usa dentro de su transacción."""
        run_id = str(uuid4())
        placeholder = self.db.placeholder
        now = datetime.now(timezone.utc)
        with self.db.connect() as connection:
            self.db.begin_write(connection)
            connection.execute(
                f"INSERT INTO {self.JOB_TABLE} (id,job_name,target_date,status,created_at) VALUES ({','.join([placeholder] * 5)})",
                (run_id, job_name, self._value(target_date), "pending", self._value(now)),
            )
            connection.commit()
        return run_id

    def claim(
        self,
        job_name: str,
        target_date: date,
        *,
        stale_after: timedelta = timedelta(hours=6),
    ) -> ClaimResult:
        """Adquiere el lock usando únicamente el estado processing.

        El índice parcial garantiza exclusión incluso si dos procesos superan
        simultáneamente las lecturas iniciales. La inserción pending y la
        transición a processing ocurren en la misma transacción.
        """

        placeholder = self.db.placeholder
        now = datetime.now(timezone.utc)
        stale_before = now - stale_after
        run_id = str(uuid4())
        connection = self.db.connect()
        try:
            self.db.begin_write(connection)
            active_rows = connection.execute(
                f"SELECT id,started_at FROM {self.JOB_TABLE} WHERE job_name={placeholder} AND status='processing'",
                (job_name,),
            ).fetchall()
            for row in active_rows:
                started_raw = row["started_at"]
                started = (
                    datetime.fromisoformat(started_raw)
                    if isinstance(started_raw, str)
                    else started_raw
                )
                if started is not None and started <= stale_before:
                    connection.execute(
                        f"UPDATE {self.JOB_TABLE} SET status='failed',finished_at={placeholder},error_message={placeholder} WHERE id={placeholder} AND status='processing'",
                        (
                            self._value(now),
                            "Recovered stale processing run before acquiring the next cycle",
                            row["id"],
                        ),
                    )
                else:
                    connection.rollback()
                    return ClaimResult(ClaimOutcome.ALREADY_PROCESSING)

            completed = self._fetchone(
                connection,
                f"SELECT id FROM {self.JOB_TABLE} WHERE job_name={placeholder} AND target_date={placeholder} AND status='completed' LIMIT 1",
                (job_name, self._value(target_date)),
            )
            if completed is not None:
                connection.rollback()
                return ClaimResult(ClaimOutcome.ALREADY_COMPLETED, completed["id"])

            connection.execute(
                f"INSERT INTO {self.JOB_TABLE} (id,job_name,target_date,status,created_at) VALUES ({','.join([placeholder] * 5)})",
                (run_id, job_name, self._value(target_date), "pending", self._value(now)),
            )
            connection.execute(
                f"UPDATE {self.JOB_TABLE} SET status='processing',started_at={placeholder} WHERE id={placeholder} AND status='pending'",
                (self._value(now), run_id),
            )
            connection.commit()
            return ClaimResult(ClaimOutcome.ACQUIRED, run_id)
        except BaseException as error:
            connection.rollback()
            if self.db.is_unique_violation(error):
                return ClaimResult(ClaimOutcome.ALREADY_PROCESSING)
            raise
        finally:
            connection.close()

    def update_status(
        self,
        run_id: str,
        status: str,
        *,
        error_message: str | None = None,
    ) -> None:
        if status not in FINAL_STATUSES:
            raise ValueError("Sólo se permiten estados finales completed o failed")
        placeholder = self.db.placeholder
        now = datetime.now(timezone.utc)
        with self.db.connect() as connection:
            self.db.begin_write(connection)
            cursor = connection.execute(
                f"UPDATE {self.JOB_TABLE} SET status={placeholder},finished_at={placeholder},error_message={placeholder} WHERE id={placeholder} AND status='processing'",
                (status, self._value(now), error_message, run_id),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise RuntimeError("La transición final no partía de processing")
            connection.commit()

    def get(self, run_id: str) -> JobRun | None:
        placeholder = self.db.placeholder
        with self.db.connect() as connection:
            row = self._fetchone(
                connection,
                f"SELECT * FROM {self.JOB_TABLE} WHERE id={placeholder}",
                (run_id,),
            )
        return self._to_model(row) if row is not None else None

    def list_for_job(self, job_name: str) -> list[JobRun]:
        placeholder = self.db.placeholder
        with self.db.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {self.JOB_TABLE} WHERE job_name={placeholder} ORDER BY created_at",
                (job_name,),
            ).fetchall()
        return [self._to_model(row) for row in rows]

    @staticmethod
    def _datetime(value: Any) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value)

    def _to_model(self, row: Any) -> JobRun:
        target = row["target_date"]
        created = self._datetime(row["created_at"])
        assert created is not None
        return JobRun(
            id=str(row["id"]),
            job_name=str(row["job_name"]),
            target_date=target if isinstance(target, date) else date.fromisoformat(target),
            status=str(row["status"]),
            started_at=self._datetime(row["started_at"]),
            finished_at=self._datetime(row["finished_at"]),
            error_message=row["error_message"],
            created_at=created,
        )
