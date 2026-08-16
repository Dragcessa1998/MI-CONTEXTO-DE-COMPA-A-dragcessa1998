"""Contratos estructurados de generación y evaluación de propuestas RFP."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from data.pipelines.rfp_intake.models import DepartmentId


class ReadabilityEvaluation(BaseModel):
    passed: bool = Field(alias="pass")
    score: float = Field(ge=0, le=100)
    details: str


class RelevanceEvaluation(BaseModel):
    passed: bool = Field(alias="pass")
    missing_aspects: list[str] = Field(default_factory=list)


class ComplianceEvaluation(BaseModel):
    passed: bool = Field(alias="pass")
    rule_ids: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    section_id: DepartmentId
    readability: ReadabilityEvaluation
    relevance: RelevanceEvaluation
    compliance: ComplianceEvaluation
    overall_pass: bool
    actionable_feedback: list[str] = Field(default_factory=list)
    iteration: int = Field(ge=1)


class GeneratedSection(BaseModel):
    department_id: DepartmentId
    draft_content: str
    evaluation_results: list[EvaluationResult] = Field(min_length=1)
    generation_iteration: int = Field(ge=1)
    needs_human_review: bool = False


class ProposalGenerationResult(BaseModel):
    ticket_id: str
    status: Literal["under_evaluation", "needs_human_review"]
    sections: list[GeneratedSection] = Field(min_length=1)
