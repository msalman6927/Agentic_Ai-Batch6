"""Eval smoke set — scripted questions over a fixed seed.

Run with: uv run pytest -q -m eval   (needs live Gemini; ~3-4 min)

Invariant checks only (event contract, tool choice, persona) — no brittle
content assertions on free-form LLM output.
"""

import asyncio
from uuid import UUID

import pytest

from medivault.db.models import Document
from medivault.dependencies import get_session_factory
from medivault.ingestion.extractor import PatientEntry
from medivault.ingestion.pipeline import ingest_document
from medivault.services import patient_service, sales_service
from medivault.services.document_service import create_document, delete_document
from tests.integration.pdf_factory import make_minimal_pdf
from tests.integration.sse_helper import collect_sse, event_names, joined_tokens

MEDICINE_PDF_TEXT = (
    "Paracetamol 500mg tablet. Indications: fever, mild pain. "
    "Dosage: one tablet every six hours, max 4g per day. "
    "Brand name: Panadol."
)

SALES_CSV = b"""sale_date,item_name,quantity,unit_price
2026-02-01,Panadol,20,5.00
2026-02-03,Brufen,8,11.00
"""


async def _seed_vault() -> dict:
    document = await create_document(
        filename="eval_medicine.pdf",
        doc_type="medicine",
        data=make_minimal_pdf(MEDICINE_PDF_TEXT),
    )
    await ingest_document(document.id)

    deadline = asyncio.get_running_loop().time() + 90.0
    factory = get_session_factory()
    while True:
        async with factory() as session:
            row = await session.get(Document, document.id)
            assert row is not None
            if row.status in {"indexed", "failed"}:
                document = row
                break
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("eval seed document never finished indexing")
        await asyncio.sleep(1.0)
    assert document.status == "indexed", document.error

    patient = await patient_service.create_patient(
        PatientEntry(
            full_name="Rahim Ullah",
            aliases=["Rahim", "رحیم"],
            conditions=["fever"],
            allergies=["penicillin"],
        )
    )

    upload = await _upload_sales_isolated()
    return {"document": document, "patient": patient, "upload_id": upload.id}


async def _upload_sales_isolated() -> UUID:
    from sqlalchemy import text as sa_text

    from medivault.dependencies import get_session_factory as _factory

    async with _factory() as session:
        await session.execute(sa_text("DELETE FROM sales"))
        await session.execute(sa_text("DELETE FROM sales_uploads"))
        await session.commit()
    upload = await sales_service.upload_sales_csv(
        filename="eval_sales.csv", content=SALES_CSV
    )
    return upload.id


def _tool_names(events) -> list[str]:
    return [e["data"].get("tool") for e in events if e["event"] == "tool_call"]


@pytest.fixture
async def seeded_vault():
    seed = await _seed_vault()
    yield seed
    await delete_document(seed["document"].id)
    await patient_service.delete_patient(seed["patient"].id)
    await sales_service.delete_upload(seed["upload_id"])


@pytest.mark.eval
async def test_eval_vault_dosage_question(client, seeded_vault) -> None:
    events = await collect_sse(
        client, {"message": "What is the dosage of Paracetamol?"}
    )
    names = event_names(events)
    assert "error" not in names, [e for e in events if e["event"] == "error"]
    assert "done" in names
    assert "confidence" in names
    sources = next(e for e in events if e["event"] == "sources")["data"]["sources"]
    assert sources, "vault question should surface retrieval sources"
    confidence = next(e for e in events if e["event"] == "confidence")
    assert confidence["data"]["from_vault"] is True
    assert "every six hours" in joined_tokens(events).lower()


@pytest.mark.eval
async def test_eval_patient_recommendation_uses_history_tools(
    client, seeded_vault
) -> None:
    patient_id = seeded_vault["patient"].id
    events = await collect_sse(
        client,
        {
            "message": (
                "Patient Rahim Ullah has fever. What should I recommend? "
                "Check his record and history first."
            ),
            "patient_id": str(patient_id),
        },
    )
    names = event_names(events)
    assert "error" not in names, [e for e in events if e["event"] == "error"]
    assert "done" in names
    called = _tool_names(events)
    assert "search_patients" in called or "get_patient_record" in called, called
    assert "penicillin" in joined_tokens(events).lower() or "allerg" in (
        joined_tokens(events).lower()
    )


@pytest.mark.eval
async def test_eval_sales_question(client, seeded_vault) -> None:
    events = await collect_sse(
        client, {"message": "How many Panadol units did we sell?"}
    )
    names = event_names(events)
    assert "error" not in names
    assert "done" in names
    assert "get_sales_summary" in _tool_names(events), _tool_names(events)
    assert "20" in joined_tokens(events)


@pytest.mark.eval
async def test_eval_greeting_stays_in_persona(client, seeded_vault) -> None:
    events = await collect_sse(client, {"message": "hi, quick one — what's 2+2?"})
    names = event_names(events)
    assert "error" not in names
    assert "done" in names
    tokens = joined_tokens(events)
    assert tokens.strip(), "persona must always reply"
    assert (
        "4" not in tokens
        or "clinical" in tokens.lower()
        or "medical" in (tokens.lower())
    )
