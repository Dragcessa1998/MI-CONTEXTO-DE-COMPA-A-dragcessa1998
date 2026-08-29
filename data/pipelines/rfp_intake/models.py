from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DepartmentId = Literal["seleccion", "capacitacion", "soporte"]


class ReadabilityMetrics(BaseModel):
    word_count: int
    sentence_count: int
    average_words_per_sentence: float
    flesch_reading_ease: float
    gunning_fog: float


class RfpMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_name: str
    client_hq: Literal["España", "Miami", "desconocida"]
    currency: Literal["EUR", "USD", "por_confirmar"]
    services_requested: list[str]
    scope: str
    volumes: dict[str, int]
    deadline: str | None = None
    budget_range: str | None = None
    departments_needed: list[DepartmentId]
    readability: ReadabilityMetrics


class Classification(BaseModel):
    is_rfp: bool
    reason: str


class DepartmentSection(BaseModel):
    department_id: DepartmentId
    department_name: str
    contact: str
    key_aspects: list[str] = Field(min_length=1)
    open_questions: list[str]
    relevant_excerpts: list[str]


class IntakeResult(BaseModel):
    classification: Classification
    metadata: RfpMetadata | None = None
    sections: list[DepartmentSection] = Field(default_factory=list)
    sales_summary: str | None = None
    markdown_path: str
