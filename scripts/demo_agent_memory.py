"""Reproducible terminal evidence for the two MEM-092 acceptance cycles."""

from __future__ import annotations

from tempfile import TemporaryDirectory
from pathlib import Path

from agent.memory import MemoryCoordinator
from agent.memory_store import SQLiteMemoryStore


def base_answer(question: str) -> dict[str, object]:
    return {"run_id": "demo-agent-run", "answer": f"Respuesta base: {question}"}


def main() -> None:
    with TemporaryDirectory() as directory:
        store = SQLiteMemoryStore(Path(directory) / "agent-memory.sqlite3")
        coordinator = MemoryCoordinator(store)
        approved_fact = (
            "Actually payroll tickets for retail clients now resolve in 24 hours, "
            "not 48 like the old SLA said."
        )
        proposed = coordinator.handle_turn(
            conversation_id="approved-cycle",
            user_id=7,
            message=approved_fact,
            answer_factory=base_answer,
        )
        print("APPROVED CYCLE")
        print("proposal:", proposed.memory_proposal.kind if proposed.memory_proposal else None)
        print("entries before confirmation:", len(store.read_all()))
        accepted = coordinator.handle_turn(
            conversation_id="approved-cycle",
            user_id=7,
            message="Sí, recuérdalo.",
            answer_factory=base_answer,
        )
        print("decision:", accepted.memory_decision)
        recalled = coordinator.handle_turn(
            conversation_id="future-cycle",
            user_id=7,
            message="¿Cuál es el SLA de payroll para clientes retail?",
            answer_factory=base_answer,
        )
        print("future recall:", recalled.recalled_memories[0].content)

        separate_store = SQLiteMemoryStore(Path(directory) / "rejected-memory.sqlite3")
        separate = MemoryCoordinator(separate_store)
        rejected_fact = (
            "That finance client always wants email confirmation before we close "
            "a support ticket."
        )
        separate.handle_turn(
            conversation_id="rejected-cycle",
            user_id=9,
            message=rejected_fact,
            answer_factory=base_answer,
        )
        rejected = separate.handle_turn(
            conversation_id="rejected-cycle",
            user_id=9,
            message="No lo recuerdes.",
            answer_factory=base_answer,
        )
        print("REJECTED CYCLE")
        print("decision:", rejected.memory_decision)
        print("entries after rejection:", len(separate_store.read_all()))
        print("audit status:", separate_store.audit_log("rejected-cycle")[0].status)


if __name__ == "__main__":
    main()
