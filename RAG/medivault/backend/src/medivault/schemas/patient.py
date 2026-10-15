from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class PatientCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=256)
    aliases: list[str] = Field(default_factory=list)
    dob: date | None = None
    gender: str | None = Field(default=None, max_length=32)
    blood_group: str | None = Field(default=None, max_length=16)
    allergies: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    notes: str | None = None


class PatientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=256)
    aliases: list[str] | None = None
    dob: date | None = None
    gender: str | None = Field(default=None, max_length=32)
    blood_group: str | None = Field(default=None, max_length=16)
    allergies: list[str] | None = None
    conditions: list[str] | None = None
    notes: str | None = None


class PatientOut(BaseModel):
    id: UUID
    full_name: str
    aliases: list[str] = Field(default_factory=list)
    dob: date | None = None
    gender: str | None = None
    blood_group: str | None = None
    allergies: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    notes: str | None = None
    source_document_id: UUID | None = None

    model_config = {"from_attributes": True}


class PatientListOut(BaseModel):
    items: list[PatientOut]
    total: int
