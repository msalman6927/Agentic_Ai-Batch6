import json
from uuid import UUID

from langchain_core.tools import tool

from medivault.dependencies import get_session_factory
from medivault.retrieval.graph import expand_patient_graph, find_patients_by_name
from medivault.services import consultation_service
from medivault.services.memory_service import search_memory as memory_search


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


@tool
async def search_patients(name: str) -> str:
    """Find patients by name (English or Roman-Urdu, matches aliases). Returns ids."""
    factory = get_session_factory()
    async with factory() as session:
        patients = await find_patients_by_name(session, name)
    if not patients:
        return f"No patient found matching '{name}'. Ask the doctor to upload records."
    payload = [
        {
            "id": str(patient.id),
            "full_name": patient.full_name,
            "aliases": patient.aliases or [],
            "conditions": patient.conditions or [],
        }
        for patient in patients[:5]
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


@tool
async def get_patient_record(patient_id: str) -> str:
    """Load a patient's full record: demographics, allergies, conditions,
    candidate medicines from the graph layer, past medicines, interactions
    and allergy flags. Call this before any treatment recommendation."""
    parsed = _parse_uuid(patient_id)
    if parsed is None:
        return "Invalid patient_id — use an id returned by search_patients."
    try:
        context = await expand_patient_graph(parsed)
    except Exception as exc:  # noqa: BLE001
        return f"Could not load patient {patient_id}: {exc}"
    return json.dumps(context.to_payload(), ensure_ascii=False, indent=2, default=str)


@tool
async def get_patient_history(patient_id: str, limit: int = 5) -> str:
    """List a patient's committed consultations (most recent first):
    diagnosis, recommended medicines, notes, follow-up."""
    parsed = _parse_uuid(patient_id)
    if parsed is None:
        return "Invalid patient_id."
    consultations = await consultation_service.get_patient_history(
        parsed, limit=min(limit, 20)
    )
    if not consultations:
        return "No committed consultations for this patient yet."
    payload = [
        {
            "date": c.created_at.isoformat() if c.created_at else None,
            "chief_complaint": c.chief_complaint,
            "diagnosis": c.diagnosis,
            "recommended": c.recommended,
            "notes": c.notes,
            "follow_up_date": (
                c.follow_up_date.isoformat() if c.follow_up_date else None
            ),
        }
        for c in consultations
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


@tool
async def search_memory(query: str, k: int = 4) -> str:
    """Search earlier chat turns (hybrid retrieval over conversation memory).

    Use when the doctor references something discussed previously.
    """
    hits = await memory_search(query, k=min(k, 10))
    if not hits:
        return "No relevant earlier conversation found."
    lines = []
    for index, hit in enumerate(hits, start=1):
        role = hit.get("role")
        snippet = hit["content"][:300]
        lines.append(f"{index}. ({role}) score={hit['score']:.3f}\n{snippet}")
    return "\n\n".join(lines)
