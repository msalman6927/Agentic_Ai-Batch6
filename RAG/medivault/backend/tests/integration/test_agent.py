from uuid import UUID

import pytest

from medivault.ingestion.extractor import MedicineEntry, PatientEntry
from medivault.services import (
    consultation_service,
    conversation_service,
    medicine_service,
    patient_service,
)
from tests.integration.sse_helper import collect_sse, event_names, joined_tokens


@pytest.mark.integration
async def test_chat_recommendation_flow(client) -> None:
    patient = await patient_service.create_patient(
        PatientEntry(
            full_name="Sara Ahmed",
            aliases=["Sara"],
            conditions=["fever"],
            allergies=[],
        )
    )
    medicine = await medicine_service.create_medicine(
        MedicineEntry(
            generic_name="Paracetamol",
            brand_name="Panadol",
            indications="fever, mild pain",
            dosage="500mg every 6 hours",
        )
    )
    try:
        events = await collect_sse(
            client,
            {
                "message": (
                    "Which medicine should I recommend for patient Sara Ahmed "
                    "who has fever? Please save the consultation too."
                ),
                "patient_id": str(patient.id),
            },
        )
        names = event_names(events)
        assert "meta" in names
        assert "done" in names, events[-5:]
        assert "error" not in names, [e for e in events if e["event"] == "error"]
        assert "token" in names, names
        assert "confidence" in names

        confidence = next(e for e in events if e["event"] == "confidence")
        assert 0.0 <= confidence["data"]["score"] <= 1.0
        assert confidence["data"]["level"] in {"high", "medium", "low"}

        done = next(e for e in events if e["event"] == "done")
        conversation_id = UUID(done["data"]["conversation_id"])

        confirm_events = [e for e in events if e["event"] == "confirm_required"]
        if confirm_events:
            draft_id = UUID(confirm_events[0]["data"]["draft_id"])
            committed = await consultation_service.confirm(draft_id)
            assert committed.status == "committed"
            assert committed.patient_id == patient.id
            history = await consultation_service.get_patient_history(patient.id)
            assert history and history[0].id == draft_id

        messages = await conversation_service.get_messages(conversation_id)
        assert [m.role for m in messages] == ["user", "assistant"]
        assert messages[1].confidence is not None
    finally:
        await patient_service.delete_patient(patient.id)
        await medicine_service.delete_medicine(medicine.id)


@pytest.mark.integration
async def test_chat_smalltalk_persona(client) -> None:
    events = await collect_sse(client, {"message": "hello"})
    names = event_names(events)
    assert "done" in names
    assert "error" not in names
    joined = joined_tokens(events).lower()
    assert joined, "persona should still reply to greetings"
