"""Adaptador HTTP fino del grafo de soporte."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from agent.graph import run_agent
from agent.guardrails import PromptSecurityError, guardrail_events, validate_user_prompt
from agent.memory import memory_coordinator, memory_store
from agent.trace_store import trace_store
from auth_models import UserRecord
from rate_limit import enforce_model_rate_limit
from security import get_current_user


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"], dependencies=[Depends(get_current_user)])


class AgentQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(max_length=500)
    conversation_id: str | None = Field(default=None, min_length=3, max_length=120)


class AgentAnswer(BaseModel):
    run_id: str
    conversation_id: str
    answer: str
    memory_proposal: dict[str, object] | None = None
    memory_decision: str | None = None
    recalled_memories: list[str] = Field(default_factory=list)


class TraceResponse(BaseModel):
    run_id: str
    started_at: str
    completed_at: str | None
    events: list[dict]


@router.post("/query", response_model=AgentAnswer, dependencies=[Depends(enforce_model_rate_limit)])
def ask_agent(
    payload: AgentQuery,
    current_user: UserRecord = Depends(get_current_user),
) -> AgentAnswer:
    try:
        question = validate_user_prompt(payload.question, source="agent.query")
        conversation_id = payload.conversation_id or f"support-user-{current_user.id}"
        result = memory_coordinator.handle_turn(
            conversation_id=conversation_id,
            user_id=current_user.id,
            message=question,
            answer_factory=run_agent,
        )
        proposal = None
        if result.memory_proposal is not None:
            proposal = {
                "proposal_id": result.memory_proposal.proposal_id,
                "kind": result.memory_proposal.kind,
                "content": result.memory_proposal.content,
                "reason": result.memory_proposal.reason,
                "status": result.memory_proposal.status,
            }
        return AgentAnswer(
            run_id=result.run_id,
            conversation_id=result.conversation_id,
            answer=result.answer,
            memory_proposal=proposal,
            memory_decision=result.memory_decision,
            recalled_memories=[entry.content for entry in result.recalled_memories],
        )
    except PromptSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("support_agent_query_failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El agente de soporte no está disponible temporalmente.",
        ) from None


@router.get("/traces/{run_id}", response_model=TraceResponse)
def get_trace(run_id: str) -> TraceResponse:
    trace = trace_store.get(run_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="La traza solicitada no existe.")
    return TraceResponse(**trace)


@router.get("/security/summary")
def get_guardrail_summary() -> dict[str, object]:
    return guardrail_events.summary()


@router.get("/memory")
def get_approved_memories() -> list[dict[str, object]]:
    """Read-only view of consolidated support memory; RAG remains untouched."""

    return [entry.model_dump(mode="json") for entry in memory_store.read_all()]


@router.get("/memory/audit")
def get_memory_audit(
    conversation_id: str | None = None,
    current_user: UserRecord = Depends(get_current_user),
) -> list[dict[str, object]]:
    """Authenticated users can inspect their own proposal/decision trail."""

    return [
        item.model_dump(mode="json")
        for item in memory_store.audit_log(conversation_id)
        if item.proposed_by == current_user.id
    ]
