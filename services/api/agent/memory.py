"""One-step self-evaluation and confirmed memory flow for first-line support."""

from __future__ import annotations

import os
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from agent.memory_store import MemoryEntry, MemoryKind, MemoryProposal, SQLiteMemoryStore


DecisionLabel = Literal["approve", "reject", "edit", "ambiguous"]
_FORBIDDEN = re.compile(
    r"\b(?:candidat[oa]s?|candidate|curr[ií]culum|curriculum|résumé|resume|cv|"
    r"entrevista|interview|rating|valoraci[oó]n|salario|salary|sueldo|headhunting negotiation|"
    r"negociaci[oó]n salarial)\b",
    re.IGNORECASE,
)
_ONE_OFF = re.compile(
    r"(?:\b(?:ticket|incidente|incidencia)\s*(?:#|id|n[úu]mero)?\s*\d+\b|"
    r"\b(?:este|ese|aquel|this|that)\s+(?:ticket|incidente|incidencia)\b|"
    r"\b(?:solo|s[oó]lo)\s+(?:esta|por esta)\s+vez\b)",
    re.IGNORECASE,
)
_CHANGE_CUE = re.compile(
    r"\b(?:actually|en realidad|corrijo|correcci[oó]n|ahora|changed?|cambi[oó]|"
    r"siempre|always|usually|normalmente|suelen|deber[ií]a|should|prefiere|wants?)\b",
    re.IGNORECASE,
)
_SUPPORT_CUE = re.compile(
    r"\b(?:ticket|incidente|incidencia|sla|escal(?:a|ar|ado|ation)|cola|queue|"
    r"soporte|support|helpdesk|email|correo|llamada|call|confirmaci[oó]n|confirmation)\b",
    re.IGNORECASE,
)
_CLIENT_PREFERENCE = re.compile(
    r"\b(?:client[ea]|empresa)\b.*\b(?:prefiere|quiere|siempre|wants?|prefers?|always)\b|"
    r"\b(?:prefiere|quiere|siempre|wants?|prefers?|always)\b.*\b(?:client[ea]|empresa)\b",
    re.IGNORECASE,
)
_INCIDENT_PATTERN = re.compile(
    r"\b(?:tickets?|incidentes?|incidencias?)\b.*\b(?:suelen|normalmente|usually|always|siempre)\b|"
    r"\b(?:suelen|normalmente|usually|always|siempre)\b.*\b(?:tickets?|incidentes?|incidencias?)\b",
    re.IGNORECASE,
)
_APPROVE = re.compile(
    r"^(?:s[ií][, ]+)?(?:recu[eé]rdalo|gu[aá]rdalo|aprueba(?:\s+la\s+propuesta)?|confirmo|"
    r"s[ií]|yes(?:,?\s+remember\s+it)?|approve)(?:[.!])?$",
    re.IGNORECASE,
)
_REJECT = re.compile(
    r"^(?:no(?:[, ]+)?(?:lo\s+)?(?:recuerdes|guardes)?|rechazo(?:\s+la\s+propuesta)?|"
    r"desc[aá]rtalo|reject)(?:[.!])?$",
    re.IGNORECASE,
)
_APPROVE_WITH_CONTINUATION = re.compile(
    r"^(?:s[ií][, ]+)?(?:recu[eé]rdalo|gu[aá]rdalo|aprueba(?:\s+la\s+propuesta)?|confirmo|"
    r"yes,?\s+remember\s+it|approve)[.!]\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_REJECT_WITH_CONTINUATION = re.compile(
    r"^(?:no[, ]+(?:lo\s+)?(?:recuerdes|guardes)|rechazo(?:\s+la\s+propuesta)?|"
    r"desc[aá]rtalo|reject)[.!]\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_EDIT = re.compile(
    r"^(?:c[aá]mbialo\s+por|recuerda\s+mejor|edita(?:\s+la\s+propuesta)?(?:\s+a)?|edit)\s*:\s*(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_TOKENS = re.compile(r"[a-z0-9áéíóúüñ]+", re.IGNORECASE)
_STOPWORDS = {
    "que", "para", "como", "cual", "cuál", "los", "las", "del", "una", "uno",
    "esta", "este", "the", "what", "which", "with", "from", "and", "por", "con",
    "de", "la", "el", "en", "un", "y", "es", "se", "me", "mi", "su",
}


class MemoryCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: MemoryKind
    memory_key: str
    content: str
    reason: str


class DecisionClassification(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: DecisionLabel
    edited_content: str | None = None
    continuation: str | None = None


class MemoryTurn(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    conversation_id: str
    answer: str
    memory_proposal: MemoryProposal | None = None
    memory_decision: Literal[
        "approved", "edited", "rejected", "rejected_ambiguous", "rejected_invalid_edit"
    ] | None = None
    recalled_memories: list[MemoryEntry] = Field(default_factory=list)


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(character for character in normalized if not unicodedata.combining(character))


def _subject(text: str) -> str:
    folded = _fold(text)
    categories = ("payroll", "nomina", "billing", "facturacion", "urgent", "urgente")
    segments = ("retail", "finance", "finanzas", "premium", "technology", "tecnologia")
    category = next((item for item in categories if item in folded), "general")
    segment = next((item for item in segments if item in folded), "general")
    aliases = {"nomina": "payroll", "facturacion": "billing", "urgente": "urgent", "finanzas": "finance", "tecnologia": "technology"}
    return f"{aliases.get(category, category)}-{aliases.get(segment, segment)}"


def evaluate_memory_candidate(message: str) -> MemoryCandidate | None:
    """Structured deterministic self-evaluation matching Nexova's allow/deny policy."""

    content = " ".join(message.strip().split())
    if (
        len(content) < 20
        or _FORBIDDEN.search(content)
        or _ONE_OFF.search(content)
        or not _CHANGE_CUE.search(content)
        or not _SUPPORT_CUE.search(content)
    ):
        return None
    if _CLIENT_PREFERENCE.search(content):
        kind: MemoryKind = "client_preference"
        reason = "Preferencia repetible de una empresa cliente de outsourcing."
    elif _INCIDENT_PATTERN.search(content):
        kind = "incident_pattern"
        reason = "Patrón conocido y repetible de incidencias de helpdesk."
    else:
        kind = "escalation_procedure"
        reason = "Corrección reutilizable de un procedimiento o SLA de soporte."
    return MemoryCandidate(
        kind=kind,
        memory_key=f"{kind}:{_subject(content)}",
        content=content,
        reason=reason,
    )


def classify_memory_decision(message: str) -> DecisionClassification:
    """Classify the whole response; ambiguity can never become approval."""

    normalized = " ".join(message.strip().split())
    approve_and_continue = _APPROVE_WITH_CONTINUATION.fullmatch(normalized)
    if approve_and_continue:
        return DecisionClassification(
            label="approve", continuation=approve_and_continue.group(1).strip()
        )
    reject_and_continue = _REJECT_WITH_CONTINUATION.fullmatch(normalized)
    if reject_and_continue:
        return DecisionClassification(
            label="reject", continuation=reject_and_continue.group(1).strip()
        )
    edit = _EDIT.fullmatch(normalized)
    if edit:
        return DecisionClassification(label="edit", edited_content=edit.group(1).strip())
    if _APPROVE.fullmatch(normalized):
        return DecisionClassification(label="approve")
    if _REJECT.fullmatch(normalized):
        return DecisionClassification(label="reject")
    return DecisionClassification(label="ambiguous")


def _token_set(text: str) -> set[str]:
    return {token for token in _TOKENS.findall(_fold(text)) if token not in _STOPWORDS and len(token) > 2}


class MemoryCoordinator:
    """Adds memory to the existing agent without creating another graph or agent identity."""

    def __init__(self, store: SQLiteMemoryStore) -> None:
        self.store = store

    def _recall(self, question: str, *, limit: int = 3) -> list[MemoryEntry]:
        question_tokens = _token_set(question)
        if not question_tokens:
            return []
        scored: list[tuple[int, MemoryEntry]] = []
        for entry in self.store.read_all():
            overlap = len(question_tokens & _token_set(entry.content))
            if overlap:
                scored.append((overlap, entry))
        recalled = [entry for _score, entry in sorted(scored, key=lambda item: (-item[0], item[1].updated_at))[:limit]]
        self.store.mark_accessed([entry.memory_id for entry in recalled])
        return recalled

    def _resolve_pending(
        self,
        pending: MemoryProposal,
        *,
        message: str,
        user_id: int,
    ) -> tuple[str, str, str | None]:
        if pending.proposed_by != user_id:
            resolved = self.store.resolve(
                pending.proposal_id,
                status="rejected_ambiguous",
                decision_label="wrong_user",
                decision_message="[different authenticated user]",
            )
            return (
                resolved.status,
                "La propuesta pendiente se descartó porque cambió el usuario autenticado.",
                message,
            )
        decision = classify_memory_decision(message)
        if decision.label == "approve":
            resolved = self.store.resolve(
                pending.proposal_id,
                status="approved",
                decision_label="approve",
                decision_message=message,
                final_content=pending.content,
            )
            self.store.write_approved(resolved, authorized_by=user_id)
            return (
                "approved",
                "Memoria aprobada y consolidada para futuras conversaciones de soporte.",
                decision.continuation,
            )
        if decision.label == "reject":
            self.store.resolve(
                pending.proposal_id,
                status="rejected",
                decision_label="reject",
                decision_message=message,
            )
            return "rejected", "Propuesta descartada; la memoria no cambió.", decision.continuation
        if decision.label == "edit":
            edited = decision.edited_content or ""
            candidate = evaluate_memory_candidate(edited)
            if candidate is None or candidate.kind != pending.kind or _FORBIDDEN.search(edited):
                self.store.resolve(
                    pending.proposal_id,
                    status="rejected_invalid_edit",
                    decision_label="edit_forbidden",
                    decision_message="[invalid or forbidden edit redacted]",
                )
                return (
                    "rejected_invalid_edit",
                    "La edición no cumple la política de memoria y se descartó.",
                    None,
                )
            resolved = self.store.resolve(
                pending.proposal_id,
                status="edited",
                decision_label="edit",
                decision_message="[explicit edit accepted]",
                final_content=edited,
            )
            self.store.write_approved(resolved, authorized_by=user_id)
            return (
                "edited",
                "Edición aprobada y consolidada para futuras conversaciones de soporte.",
                decision.continuation,
            )
        self.store.resolve(
            pending.proposal_id,
            status="rejected_ambiguous",
            decision_label="ambiguous",
            decision_message="[ambiguous response; no approval inferred]",
        )
        return (
            "rejected_ambiguous",
            "La respuesta no confirmó la propuesta; se descartó por seguridad.",
            message,
        )

    def handle_turn(
        self,
        *,
        conversation_id: str,
        user_id: int,
        message: str,
        answer_factory: Callable[[str], dict[str, object]],
    ) -> MemoryTurn:
        self.store.consolidate()
        pending = self.store.pending(conversation_id)
        memory_decision = None
        decision_notice = None
        if pending is not None:
            decision, decision_notice, continuation = self._resolve_pending(
                pending, message=message, user_id=user_id
            )
            memory_decision = decision
            self.store.consolidate()
            if continuation is None:
                return MemoryTurn(
                    run_id=f"memory_{uuid4().hex}",
                    conversation_id=conversation_id,
                    answer=decision_notice,
                    memory_decision=decision,
                )
            message = continuation

        result = answer_factory(message)
        run_id = str(result["run_id"])
        answer = str(result["answer"])
        recalled = self._recall(message)
        if recalled:
            facts = "\n".join(f"- {entry.content}" for entry in recalled)
            answer = f"{answer}\n\nMemoria aprobada relevante:\n{facts}"
        if decision_notice is not None:
            answer = f"{decision_notice}\n\n{answer}"

        proposal = None
        candidate = evaluate_memory_candidate(message)
        if candidate is not None and self.store.pending(conversation_id) is None:
            proposal = self.store.propose(
                conversation_id=conversation_id,
                proposed_by=user_id,
                memory_key=candidate.memory_key,
                kind=candidate.kind,
                content=candidate.content,
                reason=candidate.reason,
                source_message=message,
            )
            answer = (
                f"{answer}\n\nHe detectado una corrección reutilizable: “{candidate.content}”. "
                "¿Quieres que la recuerde para futuras conversaciones? Responde de forma explícita "
                "con ‘sí, recuérdalo’, ‘no lo recuerdes’ o ‘cámbialo por: …’."
            )
        return MemoryTurn(
            run_id=run_id,
            conversation_id=conversation_id,
            answer=answer,
            memory_proposal=proposal,
            memory_decision=memory_decision,
            recalled_memories=recalled,
        )


def default_memory_path() -> Path:
    configured = os.getenv("NEXOVA_AGENT_MEMORY_DB")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "data" / "agent_memory.sqlite3"


memory_store = SQLiteMemoryStore(default_memory_path())
memory_coordinator = MemoryCoordinator(memory_store)


__all__ = [
    "DecisionClassification",
    "MemoryCandidate",
    "MemoryCoordinator",
    "MemoryTurn",
    "classify_memory_decision",
    "evaluate_memory_candidate",
    "memory_coordinator",
    "memory_store",
]
