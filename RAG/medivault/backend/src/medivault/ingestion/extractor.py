import logging
from datetime import date
from typing import Literal, cast

from pydantic import BaseModel, Field

from medivault.llm.chat import get_chat_model

logger = logging.getLogger(__name__)

MAX_EXTRACT_CHARS = 24_000

MEDICINE_SYSTEM = (
    "You are a medical data-entry assistant. Extract every distinct medicine "
    "mentioned in the text into structured fields. Keep the original language "
    "(English or Urdu/Roman-Urdu) of each field. Only extract what is present — "
    "never invent values. List brand/generic aliases found in the text."
)

PATIENT_SYSTEM = (
    "You are a medical records assistant. Extract every distinct patient block "
    "into structured fields. Preserve names exactly (including Urdu/Roman-Urdu "
    "variants) in aliases. List allergies and conditions as short phrases. "
    "Only extract what is present — never invent values."
)


class InteractionEntry(BaseModel):
    with_medicine: str = Field(description="Other medicine name involved")
    severity: Literal["mild", "moderate", "severe", "contraindicated"]
    description: str | None = None


class MedicineEntry(BaseModel):
    generic_name: str
    brand_name: str | None = None
    drug_class: str | None = None
    indications: str | None = None
    dosage: str | None = None
    route: str | None = None
    contraindications: str | None = None
    warnings: str | None = None
    side_effects: str | None = None
    interactions: list[InteractionEntry] = Field(default_factory=list)


class MedicineExtraction(BaseModel):
    medicines: list[MedicineEntry] = Field(default_factory=list)


class PatientEntry(BaseModel):
    full_name: str
    aliases: list[str] = Field(default_factory=list)
    dob: str | None = None
    gender: str | None = None
    blood_group: str | None = None
    allergies: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    notes: str | None = None


class PatientExtraction(BaseModel):
    patients: list[PatientEntry] = Field(default_factory=list)


def parse_dob(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


async def _structured_invoke[T: BaseModel](
    schema: type[T], system: str, text: str
) -> T:
    model = get_chat_model(temperature=0.0)
    structured = model.with_structured_output(schema)
    clipped = text[:MAX_EXTRACT_CHARS]
    result = await structured.ainvoke([("system", system), ("human", clipped)])
    return cast(T, result)


async def extract_medicines(text: str) -> list[MedicineEntry]:
    try:
        extraction = await _structured_invoke(MedicineExtraction, MEDICINE_SYSTEM, text)
        return extraction.medicines
    except Exception as exc:  # noqa: BLE001
        logger.warning("medicine extraction failed: %s", exc)
        return []


async def extract_patients(text: str) -> list[PatientEntry]:
    try:
        extraction = await _structured_invoke(PatientExtraction, PATIENT_SYSTEM, text)
        return extraction.patients
    except Exception as exc:  # noqa: BLE001
        logger.warning("patient extraction failed: %s", exc)
        return []
