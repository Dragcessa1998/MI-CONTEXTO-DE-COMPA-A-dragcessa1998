"""Contratos de aprobación humana, arbitraje y documento final RFP."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from data.pipelines.rfp_intake.models import DepartmentId


ApprovalDecision = Literal["approve", "reject", "request_changes"]
ApprovalStatus = Literal["pending", "approved", "rejected"]


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ApprovalDecision
    feedback: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_feedback_for_non_approval(self) -> "ApprovalDecisionRequest":
        if self.decision != "approve" and not (self.feedback or "").strip():
            raise ValueError("feedback es obligatorio al rechazar o solicitar cambios")
        return self


class ArbitrationFinding(BaseModel):
    trigger_id: Literal["ttc-vs-training-window", "support-sla-missing", "currency-mismatch"]
    departments: list[DepartmentId] = Field(min_length=1)
    arbiter: str
    resolution: str


class TraceEvent(BaseModel):
    agent: str
    input: dict[str, Any]
    output: dict[str, Any]
    timestamp: datetime


class FinalDocument(BaseModel):
    ticket_id: str
    content: str
    file_path: str
    currency: Literal["EUR", "USD"]
    sections: list[DepartmentId] = Field(min_length=1)
    generated_at: datetime


class ApprovalBranchResult(BaseModel):
    ticket_id: str
    department_id: DepartmentId
    thread_id: str
    approval_status: ApprovalStatus
    approval_iteration: int = Field(ge=0)
    feedback: str | None = None
    draft_content: str
    interrupted: bool
    interrupt: dict[str, Any] | None = None
    conflicts: list[ArbitrationFinding] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=list)
