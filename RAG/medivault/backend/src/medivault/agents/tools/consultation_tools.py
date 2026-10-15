import json
from datetime import date
from uuid import UUID

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from medivault.services import consultation_service
from medivault.utils.errors import ValidationFailure


class RecommendedItem(BaseModel):
    medicine_id: str | None = Field(default=None, description="Medicine UUID if known")
    name: str = Field(description="Medicine name as the doctor should see it")
    dose: str | None = Field(default=None, description="e.g. 500mg")
    frequency: str | None = Field(default=None, description="e.g. twice daily")
    duration: str | None = Field(default=None, description="e.g. 5 days")


@tool
async def record_consultation(
    patient_id: str,
    diagnosis: str,
    recommended: list[RecommendedItem],
    chief_complaint: str = "",
    notes: str = "",
    follow_up_date: str | None = None,
) -> str:
    """Create a DRAFT consultation for a patient (the doctor confirms it separately).

    Call only after loading the patient record. Include the medicines you recommended
    with dose/frequency/duration. Returns the draft_id for confirmation.
    """
    try:
        parsed = UUID(patient_id)
    except ValueError:
        return "Invalid patient_id."
    if not recommended:
        return "Recommendation list is empty — nothing to save."
    follow_up: date | None = None
    if follow_up_date:
        try:
            follow_up = date.fromisoformat(follow_up_date)
        except ValueError:
            return "follow_up_date must be ISO format YYYY-MM-DD."
    try:
        consultation = await consultation_service.create_draft(
            patient_id=parsed,
            chief_complaint=chief_complaint or None,
            diagnosis=diagnosis,
            recommended=[item.model_dump() for item in recommended],
            notes=notes or None,
            follow_up_date=follow_up,
            confidence=None,
        )
    except ValidationFailure as exc:
        return f"Could not create draft: {exc.detail}"
    return json.dumps(
        {
            "draft_id": str(consultation.id),
            "status": consultation.status,
            "patient_id": str(consultation.patient_id),
            "diagnosis": consultation.diagnosis,
            "recommended": consultation.recommended,
            "note": "Draft created. The doctor must call "
            "POST /consultations/confirm with this draft_id to commit it.",
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
