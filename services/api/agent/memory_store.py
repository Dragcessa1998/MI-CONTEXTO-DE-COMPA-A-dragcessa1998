"""Persistent, auditable memory store kept separate from Nexova's RAG corpus."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict


MemoryKind = Literal["escalation_procedure", "client_preference", "incident_pattern"]
ProposalStatus = Literal[
    "pending",
    "approved",
    "edited",
    "rejected",
    "rejected_ambiguous",
    "rejected_invalid_edit",
    "expired",
]


def _now() -> str:
    return datetime.now(UTC).isoformat()


class MemoryProposal(BaseModel):
    model_config = ConfigDict(frozen=True)

    proposal_id: str
    conversation_id: str
    proposed_by: int
    business_line: Literal["support"] = "support"
    memory_key: str
    kind: MemoryKind
    content: str
    reason: str
    source_message: str
    created_at: str
    status: ProposalStatus
    decision_label: str | None = None
    decision_message: str | None = None
    decided_at: str | None = None
    final_content: str | None = None


class MemoryEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    memory_id: str
    business_line: Literal["support"] = "support"
    memory_key: str
    kind: MemoryKind
    content: str
    source_proposal_id: str
    authorized_by: int
    created_at: str
    updated_at: str
    last_accessed_at: str
    access_count: int


class SQLiteMemoryStore:
    """Explicit read/write boundary with bounded consolidation and immutable audit rows."""

    def __init__(self, path: str | Path, *, clock: Callable[[], str] = _now) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    proposed_by INTEGER NOT NULL,
                    business_line TEXT NOT NULL CHECK (business_line = 'support'),
                    memory_key TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    source_message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    decision_label TEXT,
                    decision_message TEXT,
                    decided_at TEXT,
                    final_content TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_pending_proposal_per_conversation
                    ON memory_proposals(conversation_id) WHERE status = 'pending';
                CREATE INDEX IF NOT EXISTS memory_proposal_audit_order
                    ON memory_proposals(created_at DESC);

                CREATE TABLE IF NOT EXISTS agent_memories (
                    memory_id TEXT PRIMARY KEY,
                    business_line TEXT NOT NULL CHECK (business_line = 'support'),
                    memory_key TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_proposal_id TEXT NOT NULL,
                    authorized_by INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_accessed_at TEXT NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    UNIQUE (business_line, memory_key),
                    FOREIGN KEY (source_proposal_id) REFERENCES memory_proposals(proposal_id)
                );
                """
            )

    @staticmethod
    def _proposal(row: sqlite3.Row) -> MemoryProposal:
        return MemoryProposal(**dict(row))

    @staticmethod
    def _entry(row: sqlite3.Row) -> MemoryEntry:
        return MemoryEntry(**dict(row))

    def pending(self, conversation_id: str) -> MemoryProposal | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM memory_proposals WHERE conversation_id = ? AND status = 'pending'",
                (conversation_id,),
            ).fetchone()
        return self._proposal(row) if row is not None else None

    def propose(
        self,
        *,
        conversation_id: str,
        proposed_by: int,
        memory_key: str,
        kind: MemoryKind,
        content: str,
        reason: str,
        source_message: str,
    ) -> MemoryProposal:
        timestamp = self._clock()
        proposal = MemoryProposal(
            proposal_id=f"memprop_{uuid4().hex}",
            conversation_id=conversation_id,
            proposed_by=proposed_by,
            memory_key=memory_key,
            kind=kind,
            content=content,
            reason=reason,
            source_message=source_message,
            created_at=timestamp,
            status="pending",
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_proposals (
                    proposal_id, conversation_id, proposed_by, business_line,
                    memory_key, kind, content, reason, source_message, created_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal.proposal_id,
                    proposal.conversation_id,
                    proposal.proposed_by,
                    proposal.business_line,
                    proposal.memory_key,
                    proposal.kind,
                    proposal.content,
                    proposal.reason,
                    proposal.source_message,
                    proposal.created_at,
                    proposal.status,
                ),
            )
        return proposal

    def resolve(
        self,
        proposal_id: str,
        *,
        status: ProposalStatus,
        decision_label: str,
        decision_message: str,
        final_content: str | None = None,
    ) -> MemoryProposal:
        if status == "pending":
            raise ValueError("A pending proposal cannot resolve to pending")
        timestamp = self._clock()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE memory_proposals
                SET status = ?, decision_label = ?, decision_message = ?,
                    decided_at = ?, final_content = ?
                WHERE proposal_id = ? AND status = 'pending'
                """,
                (status, decision_label, decision_message, timestamp, final_content, proposal_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("The proposal is missing or already resolved")
            row = connection.execute(
                "SELECT * FROM memory_proposals WHERE proposal_id = ?", (proposal_id,)
            ).fetchone()
        assert row is not None
        return self._proposal(row)

    def write_approved(self, proposal: MemoryProposal, *, authorized_by: int) -> MemoryEntry:
        if proposal.status not in {"approved", "edited"}:
            raise ValueError("Only an approved or edited proposal may enter memory")
        if proposal.proposed_by != authorized_by:
            raise PermissionError("The approving user must own the pending proposal")
        content = proposal.final_content or proposal.content
        timestamp = self._clock()
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                "SELECT memory_id, created_at FROM agent_memories WHERE business_line = ? AND memory_key = ?",
                (proposal.business_line, proposal.memory_key),
            ).fetchone()
            memory_id = str(existing["memory_id"]) if existing else f"memory_{uuid4().hex}"
            created_at = str(existing["created_at"]) if existing else timestamp
            connection.execute(
                """
                INSERT INTO agent_memories (
                    memory_id, business_line, memory_key, kind, content,
                    source_proposal_id, authorized_by, created_at, updated_at,
                    last_accessed_at, access_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(business_line, memory_key) DO UPDATE SET
                    kind = excluded.kind,
                    content = excluded.content,
                    source_proposal_id = excluded.source_proposal_id,
                    authorized_by = excluded.authorized_by,
                    updated_at = excluded.updated_at,
                    last_accessed_at = excluded.last_accessed_at,
                    access_count = 0
                """,
                (
                    memory_id,
                    proposal.business_line,
                    proposal.memory_key,
                    proposal.kind,
                    content,
                    proposal.proposal_id,
                    authorized_by,
                    created_at,
                    timestamp,
                    timestamp,
                ),
            )
            row = connection.execute(
                "SELECT * FROM agent_memories WHERE memory_id = ?", (memory_id,)
            ).fetchone()
        assert row is not None
        return self._entry(row)

    def read_all(self, *, business_line: Literal["support"] = "support") -> list[MemoryEntry]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_memories WHERE business_line = ? ORDER BY updated_at DESC",
                (business_line,),
            ).fetchall()
        return [self._entry(row) for row in rows]

    def mark_accessed(self, memory_ids: list[str]) -> None:
        if not memory_ids:
            return
        placeholders = ",".join("?" for _ in memory_ids)
        with self._lock, self._connect() as connection:
            connection.execute(
                f"""UPDATE agent_memories
                    SET access_count = access_count + 1, last_accessed_at = ?
                    WHERE memory_id IN ({placeholders})""",
                (self._clock(), *memory_ids),
            )

    def audit_log(self, conversation_id: str | None = None) -> list[MemoryProposal]:
        query = "SELECT * FROM memory_proposals"
        parameters: tuple[str, ...] = ()
        if conversation_id is not None:
            query += " WHERE conversation_id = ?"
            parameters = (conversation_id,)
        query += " ORDER BY created_at ASC"
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._proposal(row) for row in rows]

    def consolidate(
        self,
        *,
        max_entries: int = 200,
        max_audit_rows: int = 1_000,
        audit_retention_days: int = 730,
        pending_ttl_hours: int = 24,
    ) -> dict[str, int]:
        """Expire abandoned proposals and bound LRU memory/audit growth."""

        now = datetime.fromisoformat(self._clock())
        pending_cutoff = (now - timedelta(hours=pending_ttl_hours)).isoformat()
        audit_cutoff = (now - timedelta(days=audit_retention_days)).isoformat()
        with self._lock, self._connect() as connection:
            expired = connection.execute(
                """
                UPDATE memory_proposals
                SET status = 'expired', decision_label = 'timeout',
                    decision_message = '[no response within retention window]', decided_at = ?
                WHERE status = 'pending' AND created_at < ?
                """,
                (self._clock(), pending_cutoff),
            ).rowcount
            entry_count = int(connection.execute("SELECT COUNT(*) FROM agent_memories").fetchone()[0])
            removed_entries = max(0, entry_count - max_entries)
            if removed_entries:
                connection.execute(
                    """
                    DELETE FROM agent_memories WHERE memory_id IN (
                        SELECT memory_id FROM agent_memories
                        ORDER BY last_accessed_at ASC, updated_at ASC LIMIT ?
                    )
                    """,
                    (removed_entries,),
                )
            audit_count = int(connection.execute("SELECT COUNT(*) FROM memory_proposals").fetchone()[0])
            audit_rows = connection.execute(
                """
                SELECT proposal_id, created_at FROM memory_proposals
                WHERE status != 'pending'
                ORDER BY created_at ASC
                """,
            ).fetchall()
            removed_audits = 0
            for row in audit_rows:
                exceeds_cap = audit_count - removed_audits > max_audit_rows
                exceeds_age = str(row["created_at"]) < audit_cutoff
                if not exceeds_cap and not exceeds_age:
                    continue
                referenced = connection.execute(
                    "SELECT 1 FROM agent_memories WHERE source_proposal_id = ?",
                    (row["proposal_id"],),
                ).fetchone()
                if referenced is None:
                    connection.execute(
                        "DELETE FROM memory_proposals WHERE proposal_id = ?",
                        (row["proposal_id"],),
                    )
                    removed_audits += 1
        return {
            "expired_proposals": expired,
            "removed_entries": removed_entries,
            "removed_audits": removed_audits,
        }


__all__ = [
    "MemoryEntry",
    "MemoryKind",
    "MemoryProposal",
    "ProposalStatus",
    "SQLiteMemoryStore",
]
