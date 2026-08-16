"""Guardrails deterministas y observabilidad para entradas de agentes Nexova."""

from __future__ import annotations

import html
import re
import unicodedata
from collections import Counter, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Literal


FailureType = Literal["structural", "content", "security"]
GuardrailAction = Literal["blocked", "neutralized"]
MAX_PROMPT_LENGTH = 500
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior|company|system)\s+(?:instructions?|polic(?:y|ies))\b", re.I),
    re.compile(r"\bforget\s+(?:the\s+)?(?:company(?:'s)?|previous|prior|system)\s+(?:instructions?|polic(?:y|ies))\b", re.I),
    re.compile(r"\b(?:reveal|show|print|return|expose)\s+(?:the\s+)?(?:system\s+prompt|api\s*key|secret|credentials?)\b", re.I),
    re.compile(r"\b(?:give|grant)\s+me\s+access\s+to\s+another\s+(?:user|client)(?:'s)?\s+account\b", re.I),
    re.compile(r"\bmark\s+me\s+as\s+(?:the\s+)?top[- ]rated\s+candidate\b", re.I),
    re.compile(r"\b(?:ignora|olvida)\s+(?:todas?\s+)?(?:las?\s+)?(?:instrucciones|pol[ií]ticas)(?:\s+(?:anteriores|del sistema|de la empresa))?\b", re.I),
    re.compile(r"\b(?:mu[eé]strame|revela)\s+(?:el\s+)?(?:prompt del sistema|secreto|clave de api|credenciales)\b", re.I),
    re.compile(r"\bdame\s+acceso\s+a\s+la\s+cuenta\s+de\s+otro\s+usuario\b", re.I),
    re.compile(r"(?:<\s*system\s*>|\[\s*system\s*\]|\bjailbreak\b|\bdo anything now\b)", re.I),
)


class PromptSecurityError(ValueError):
    def __init__(self, detail: str, failure_type: FailureType = "security") -> None:
        super().__init__(detail)
        self.failure_type = failure_type


@dataclass(frozen=True, slots=True)
class GuardrailEvent:
    timestamp: str
    action: GuardrailAction
    failure_type: FailureType
    source: str
    rule_id: str


class GuardrailEventStore:
    def __init__(self, max_events: int = 500) -> None:
        self._events: deque[GuardrailEvent] = deque(maxlen=max_events)
        self._lock = Lock()

    def record(
        self,
        action: GuardrailAction,
        failure_type: FailureType,
        source: str,
        rule_id: str,
    ) -> None:
        with self._lock:
            self._events.append(GuardrailEvent(
                timestamp=datetime.now(UTC).isoformat(),
                action=action,
                failure_type=failure_type,
                source=source,
                rule_id=rule_id,
            ))

    def summary(self) -> dict[str, object]:
        with self._lock:
            events = tuple(self._events)
        return {
            "total": len(events),
            "by_action": dict(Counter(event.action for event in events)),
            "by_failure_type": dict(Counter(event.failure_type for event in events)),
            "by_rule": dict(Counter(event.rule_id for event in events)),
        }

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


guardrail_events = GuardrailEventStore()


def _normalize(text: str) -> str:
    return _CONTROL_CHARS.sub("", unicodedata.normalize("NFKC", text)).strip()


def _injection_match(text: str) -> re.Pattern[str] | None:
    return next((pattern for pattern in _INJECTION_PATTERNS if pattern.search(text)), None)


def validate_user_prompt(text: str, *, source: str) -> str:
    normalized = _normalize(text)
    if not normalized:
        guardrail_events.record("blocked", "structural", source, "INPUT-EMPTY")
        raise PromptSecurityError("La solicitud no puede estar vacía.", "structural")
    if len(normalized) > MAX_PROMPT_LENGTH:
        guardrail_events.record("blocked", "structural", source, "INPUT-LENGTH")
        raise PromptSecurityError("La solicitud supera el límite permitido.", "structural")
    if _injection_match(normalized) is not None:
        guardrail_events.record("blocked", "security", source, "PROMPT-INJECTION")
        raise PromptSecurityError(
            "La solicitud contiene instrucciones que intentan alterar las políticas del agente.",
            "security",
        )
    return normalized


def isolate_external_content(text: str, *, source: str) -> str:
    """Escapa markup y neutraliza líneas que intentan convertirse en instrucciones."""

    normalized = _normalize(text)
    safe_lines: list[str] = []
    neutralized = False
    for line in normalized.splitlines() or [normalized]:
        if _injection_match(line) is not None:
            safe_lines.append("[INSTRUCCIÓN EXTERNA NEUTRALIZADA]")
            neutralized = True
        else:
            safe_lines.append(html.escape(line, quote=True))
    if neutralized:
        guardrail_events.record("neutralized", "security", source, "INDIRECT-INJECTION")
    return "\n".join(safe_lines)


__all__ = [
    "PromptSecurityError",
    "guardrail_events",
    "isolate_external_content",
    "validate_user_prompt",
]
