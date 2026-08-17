"""Guardrails deterministas y observabilidad para entradas de agentes Nexova."""

from __future__ import annotations

import html
import logging
import re
import unicodedata
from collections import Counter, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Literal
from zoneinfo import ZoneInfo


FailureType = Literal["structural", "content", "security"]
GuardrailAction = Literal["blocked", "neutralized", "redirected"]
InputCategory = Literal["domain", "casual", "personal_task", "jailbreak", "cross_account"]
MAX_PROMPT_LENGTH = 500
MAX_OUTPUT_LENGTH = 5_000
SUPPORT_REDIRECT = "Por cierto, ¿cómo puedo ayudarte hoy con tu ticket de soporte?"
PERSONAL_REFUSAL = (
    "No puedo realizar tareas personales o ajenas al soporte. "
    "Puedo ayudarte con tickets, incidencias, procedimientos, SLAs o preguntas frecuentes de soporte."
)
SECURITY_REFUSAL = (
    "No puedo cambiar mis instrucciones ni operar sin las políticas de Nexova. "
    "Puedo ayudarte con una consulta legítima de soporte."
)
CROSS_ACCOUNT_REFUSAL = (
    "No puedo acceder, imitar ni revelar información de otra empresa cliente. "
    "Sólo puedo ayudarte con la cuenta de soporte autenticada en esta sesión."
)
SAFE_OUTPUT_FALLBACK = (
    "No puedo mostrar esa respuesta porque no superó los controles de seguridad. "
    "Puedo ayudarte con tu ticket usando únicamente datos autorizados."
)
logger = logging.getLogger("nexova.agent.guardrails")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+)?(?:your\s+)?(?:previous|prior|company|system)\s+(?:instructions?|polic(?:y|ies))\b", re.I),
    re.compile(r"\bforget\s+(?:the\s+)?(?:company(?:'s)?|previous|prior|system)\s+(?:instructions?|polic(?:y|ies))\b", re.I),
    re.compile(r"\b(?:reveal|show|print|return|expose)\s+(?:the\s+)?(?:system\s+prompt|api\s*key|secret|credentials?)\b", re.I),
    re.compile(r"\b(?:give|grant)\s+me\s+access\s+to\s+another\s+(?:user|client)(?:'s)?\s+account\b", re.I),
    re.compile(r"\bmark\s+me\s+as\s+(?:the\s+)?top[- ]rated\s+candidate\b", re.I),
    re.compile(r"\bforget\s+that\s+you\s+(?:work|are\s+working)\s+for\b", re.I),
    re.compile(r"\bact\s+as\s+if\s+you\s+(?:had|have)\s+no\s+rules\b", re.I),
    re.compile(r"\b(?:ignora|olvida)\s+(?:todas?\s+)?(?:las?\s+)?(?:instrucciones|pol[ií]ticas)(?:\s+(?:anteriores|del sistema|de la empresa))?\b", re.I),
    re.compile(r"\b(?:mu[eé]strame|revela)\s+(?:el\s+)?(?:prompt del sistema|secreto|clave de api|credenciales)\b", re.I),
    re.compile(r"\bdame\s+acceso\s+a\s+la\s+cuenta\s+de\s+otro\s+usuario\b", re.I),
    re.compile(r"(?:<\s*system\s*>|\[\s*system\s*\]|\bjailbreak\b|\bdo anything now\b)", re.I),
)
_DOMAIN_PATTERNS = re.compile(
    r"\b(?:ticket|incidente|incidencia|support|soporte|sla|procedimiento|procedure|"
    r"faq|pregunta frecuente|estado|status|helpdesk|reclamaci[oó]n|aver[ií]a|garant[ií]a)\b",
    re.IGNORECASE,
)
_PERSONAL_PATTERNS = re.compile(
    r"\b(?:ensayo|essay|tarea (?:universitaria|escolar)|university homework|homework|"
    r"poema|poem|c[oó]digo para|code for|programa para|terapeuta|therapist|terapia|"
    r"consejo personal|personal advice|carta de amor|love letter|curr[ií]culum para m[ií]|"
    r"receta de cocina|meal plan)\b",
    re.IGNORECASE,
)
_CROSS_ACCOUNT_PATTERNS = re.compile(
    r"\b(?:otra|otro|another|other)\s+(?:empresa|company|cliente|client|cuenta|account)\b|"
    r"\b(?:empresa|company|cliente|client|cuenta|account)\s+(?:ajena|de otro|distinta)\b|"
    r"\bact(?:[úu]a|)\s+como\s+si\s+fueras?\s+(?:soporte|support)\s+(?:de|for)\b",
    re.IGNORECASE,
)
_GREETING = re.compile(
    r"^(?:hola|buenos d[ií]as|buenas tardes|buenas noches|hello|hi|hey|"
    r"c[oó]mo est[aá]s|how are you)[?!. ,]*$",
    re.IGNORECASE,
)
_TIME_QUERY = re.compile(
    r"\b(?:qu[eé]\s+hora\s+es|hora\s+en|what\s+time\s+is\s+it\s+in)\s+(?:en\s+)?"
    r"(?P<city>valencia|miami|tokyo|tokio)\b",
    re.IGNORECASE,
)
_SENSITIVE_OUTPUT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "OUTPUT-SYSTEM-PROMPT",
        re.compile(
            r"(?:AUTHORITY ORDER|TENANT AND DATA BOUNDARIES|SUPPORT_SYSTEM_PROMPT|"
            r"here (?:is|are) (?:my|the) system (?:prompt|instructions)|"
            r"mis instrucciones del sistema son)",
            re.IGNORECASE,
        ),
    ),
    (
        "OUTPUT-CREDENTIAL",
        re.compile(
            r"(?:\bBearer\s+[A-Za-z0-9._~-]{16,}|\b(?:api[_ -]?key|access[_ -]?token|"
            r"client[_ -]?secret)\s*[:=]\s*\S+|\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.)",
            re.IGNORECASE,
        ),
    ),
    (
        "OUTPUT-CONTRACT-TERMS",
        re.compile(
            r"\b(?:sla\s+penalt(?:y|ies)|penalizaci[oó]n(?:es)?\s+(?:del\s+)?sla|"
            r"outsourcing\s+contract\s+(?:rate|fee)|tarifa\s+(?:del\s+)?contrato\s+de\s+outsourcing|"
            r"commercial\s+terms\s+of\s+the\s+outsourcing\s+contract)\b",
            re.IGNORECASE,
        ),
    ),
)


class PromptSecurityError(ValueError):
    def __init__(self, detail: str, failure_type: FailureType = "security") -> None:
        super().__init__(detail)
        self.failure_type = failure_type


class OutputSecurityError(ValueError):
    def __init__(self, detail: str, rule_id: str) -> None:
        super().__init__(detail)
        self.rule_id = rule_id


@dataclass(frozen=True, slots=True)
class InputGuardDecision:
    category: InputCategory
    normalized: str
    proceed: bool
    response: str | None = None


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
        logger.warning(
            "guardrail_triggered action=%s failure_type=%s source=%s rule_id=%s",
            action,
            failure_type,
            source,
            rule_id,
        )

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


def _casual_answer(normalized: str) -> str:
    if _GREETING.fullmatch(normalized):
        return f"Hola. Estoy disponible para ayudarte. {SUPPORT_REDIRECT}"
    time_match = _TIME_QUERY.search(normalized)
    if time_match:
        city = time_match.group("city").lower()
        zones = {
            "valencia": ("Europe/Madrid", "Valencia"),
            "miami": ("America/New_York", "Miami"),
            "tokyo": ("Asia/Tokyo", "Tokio"),
            "tokio": ("Asia/Tokyo", "Tokio"),
        }
        zone, label = zones[city]
        local_time = datetime.now(ZoneInfo(zone)).strftime("%H:%M")
        return f"En {label} son aproximadamente las {local_time}. {SUPPORT_REDIRECT}"
    return f"Puedo responder esa consulta general sólo de forma breve. {SUPPORT_REDIRECT}"


def evaluate_support_input(text: str, *, source: str) -> InputGuardDecision:
    """Classify scope and abuse before RAG, MCP, memory, or a model is invoked."""

    normalized = _normalize(text)
    if not normalized:
        guardrail_events.record("blocked", "structural", source, "INPUT-EMPTY")
        return InputGuardDecision("personal_task", normalized, False, "La solicitud no puede estar vacía.")
    if len(normalized) > MAX_PROMPT_LENGTH:
        guardrail_events.record("blocked", "structural", source, "INPUT-LENGTH")
        return InputGuardDecision("personal_task", normalized, False, "La solicitud supera el límite permitido.")
    if _injection_match(normalized) is not None:
        guardrail_events.record("blocked", "security", source, "PROMPT-INJECTION")
        return InputGuardDecision("jailbreak", normalized, False, SECURITY_REFUSAL)
    if _CROSS_ACCOUNT_PATTERNS.search(normalized):
        guardrail_events.record("blocked", "security", source, "CROSS-ACCOUNT")
        return InputGuardDecision("cross_account", normalized, False, CROSS_ACCOUNT_REFUSAL)
    if _PERSONAL_PATTERNS.search(normalized):
        guardrail_events.record("blocked", "content", source, "PERSONAL-USE")
        return InputGuardDecision("personal_task", normalized, False, PERSONAL_REFUSAL)
    if _DOMAIN_PATTERNS.search(normalized):
        return InputGuardDecision("domain", normalized, True)
    guardrail_events.record("redirected", "content", source, "OUT-OF-DOMAIN-REDIRECT")
    return InputGuardDecision("casual", normalized, False, _casual_answer(normalized))


def validate_agent_output(text: str, *, source: str, authenticated_client_id: str) -> str:
    """Block malformed, credential-bearing, contract, prompt, or cross-tenant output."""

    normalized = _normalize(text)
    if not normalized or len(normalized) > MAX_OUTPUT_LENGTH:
        rule_id = "OUTPUT-EMPTY" if not normalized else "OUTPUT-LENGTH"
        guardrail_events.record("blocked", "structural", source, rule_id)
        raise OutputSecurityError("The model output has an invalid structure", rule_id)
    for rule_id, pattern in _SENSITIVE_OUTPUT_PATTERNS:
        if pattern.search(normalized):
            guardrail_events.record("blocked", "content", source, rule_id)
            raise OutputSecurityError("The model output contains protected information", rule_id)
    tenant_tags = re.findall(r"\[client:([A-Za-z0-9_-]+)\]", normalized, re.IGNORECASE)
    if any(client_id != authenticated_client_id for client_id in tenant_tags):
        guardrail_events.record("blocked", "security", source, "OUTPUT-CROSS-ACCOUNT")
        raise OutputSecurityError("The model output crosses the authenticated tenant", "OUTPUT-CROSS-ACCOUNT")
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
    "CROSS_ACCOUNT_REFUSAL",
    "InputGuardDecision",
    "OutputSecurityError",
    "PERSONAL_REFUSAL",
    "PromptSecurityError",
    "SAFE_OUTPUT_FALLBACK",
    "SECURITY_REFUSAL",
    "SUPPORT_REDIRECT",
    "evaluate_support_input",
    "guardrail_events",
    "isolate_external_content",
    "validate_agent_output",
    "validate_user_prompt",
]
