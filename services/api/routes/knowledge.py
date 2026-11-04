"""Adaptador HTTP fino para la base de conocimiento comercial."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from data.pipelines.rag import query


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class KnowledgeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=2, max_length=500)


class KnowledgeAnswer(BaseModel):
    answer: str


@router.post("/query", response_model=KnowledgeAnswer)
def ask_knowledge_base(payload: KnowledgeQuery) -> KnowledgeAnswer:
    """Invoca el pipeline; no reproduce retrieval ni expone chunks/scores."""

    try:
        return KnowledgeAnswer(answer=query(payload.question))
    except Exception:
        logger.exception("knowledge_query_failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El asistente de conocimiento no está disponible temporalmente.",
        ) from None
