"""Adaptador HTTP fino para la base de conocimiento comercial."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from agent.guardrails import PromptSecurityError, validate_user_prompt
from data.pipelines.rag import query
from rate_limit import enforce_model_rate_limit
from security import get_current_user


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge", tags=["knowledge"], dependencies=[Depends(get_current_user)])


class KnowledgeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=2, max_length=500)


class KnowledgeAnswer(BaseModel):
    answer: str


@router.post("/query", response_model=KnowledgeAnswer, dependencies=[Depends(enforce_model_rate_limit)])
def ask_knowledge_base(payload: KnowledgeQuery) -> KnowledgeAnswer:
    """Invoca el pipeline; no reproduce retrieval ni expone chunks/scores."""

    try:
        return KnowledgeAnswer(answer=query(validate_user_prompt(payload.question, source="knowledge.query")))
    except PromptSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("knowledge_query_failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El asistente de conocimiento no está disponible temporalmente.",
        ) from None
