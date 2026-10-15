from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RecommendedItemOut(BaseModel):
    medicine_id: UUID | None = None
    name: str
    dose: str | None = None
    frequency: str | None = None
    duration: str | None = None


class ConsultationOut(BaseModel):
    id: UUID
    patient_id: UUID
    chief_complaint: str | None = None
    diagnosis: str | None = None
    recommended: list[RecommendedItemOut] = Field(default_factory=list)
    notes: str | None = None
    follow_up_date: date | None = None
    status: Literal["draft", "committed", "cancelled"]
    confidence: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConsultationListOut(BaseModel):
    items: list[ConsultationOut]


class ConfirmRequest(BaseModel):
    draft_id: UUID


class ManualConsultationIn(BaseModel):
    patient_id: UUID
    chief_complaint: str | None = None
    diagnosis: str | None = None
    recommended: list[RecommendedItemOut] = Field(default_factory=list)
    notes: str | None = None
    follow_up_date: date | None = None
