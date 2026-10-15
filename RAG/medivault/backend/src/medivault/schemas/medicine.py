from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

SeverityLiteral = Literal["mild", "moderate", "severe", "contraindicated"]


class InteractionIn(BaseModel):
    with_medicine: str
    severity: SeverityLiteral
    description: str | None = None


class MedicineCreate(BaseModel):
    generic_name: str = Field(min_length=1, max_length=256)
    brand_name: str | None = Field(default=None, max_length=256)
    aliases: list[str] = Field(default_factory=list)
    drug_class: str | None = Field(default=None, max_length=256)
    indications: str | None = None
    dosage: str | None = None
    route: str | None = Field(default=None, max_length=128)
    contraindications: str | None = None
    warnings: str | None = None
    side_effects: str | None = None
    interactions_notes: str | None = None


class MedicineUpdate(BaseModel):
    generic_name: str | None = Field(default=None, min_length=1, max_length=256)
    brand_name: str | None = Field(default=None, max_length=256)
    drug_class: str | None = Field(default=None, max_length=256)
    indications: str | None = None
    dosage: str | None = None
    route: str | None = Field(default=None, max_length=128)
    contraindications: str | None = None
    warnings: str | None = None
    side_effects: str | None = None
    interactions_notes: str | None = None


class MedicineOut(BaseModel):
    id: UUID
    generic_name: str
    brand_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    drug_class: str | None = None
    indications: str | None = None
    dosage: str | None = None
    route: str | None = None
    contraindications: str | None = None
    warnings: str | None = None
    side_effects: str | None = None
    interactions_notes: str | None = None
    source_document_id: UUID | None = None

    model_config = {"from_attributes": True}


class MedicineListOut(BaseModel):
    items: list[MedicineOut]
    total: int
