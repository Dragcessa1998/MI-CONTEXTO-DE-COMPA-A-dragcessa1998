"""Adaptador HTTP fino del grafo de soporte."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from agent.graph import run_agent
from agent.trace_store import trace_store


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])


class AgentQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(max_length=500)


class AgentAnswer(BaseModel):
    run_id: str
    answer: str


class TraceResponse(BaseModel):
    run_id: str
    started_at: str
    completed_at: str | None
    events: list[dict]


@router.post("/query", response_model=AgentAnswer)
def ask_agent(payload: AgentQuery) -> AgentAnswer:
    try:
        result = run_agent(payload.question)
        return AgentAnswer(run_id=result["run_id"], answer=result["answer"])
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
