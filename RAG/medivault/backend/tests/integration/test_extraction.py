import asyncio

import pytest
from sqlalchemy import select

from medivault.db.models import Medicine, MedicineInteraction
from medivault.dependencies import get_session_factory
from medivault.ingestion.pipeline import ingest_document
from medivault.services.document_service import create_document, delete_document
from tests.integration.pdf_factory import make_minimal_pdf

MEDICINE_PDF_TEXT = """\
Paracetamol 500mg (Panadol)
Drug class: Analgesic / Antipyretic
Indications: fever, headache, mild to moderate pain
Dosage: 1-2 tablets every 6 hours, max 4g daily
Contraindications: severe hepatic impairment
Ibuprofen 400mg (Brufen)
Drug class: NSAID
Indications: pain, inflammation, fever
Dosage: one tablet every 8 hours after food
Warnings: may cause gastric irritation; avoid with aspirin sensitivity
Interaction note: Ibuprofen may interact with Paracetamol - moderate severity,
usually safe at standard doses but monitor liver loading.
"""


async def _wait_indexed(document_id, max_wait_seconds: float = 120.0):
    factory = get_session_factory()
    deadline = asyncio.get_running_loop().time() + max_wait_seconds
    while True:
        async with factory() as session:
            from medivault.db.models import Document

            document = await session.get(Document, document_id)
            assert document is not None
            if document.status in {"indexed", "failed"}:
                return document
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("ingest timed out")
        await asyncio.sleep(1.0)


@pytest.mark.integration
async def test_extraction_creates_medicine_rows() -> None:
    document = await create_document(
        filename="catalog.pdf",
        doc_type="medicine",
        data=make_minimal_pdf(MEDICINE_PDF_TEXT),
    )
    try:
        await ingest_document(document.id)
        document = await _wait_indexed(document.id)
        assert document.status == "indexed", document.error

        factory = get_session_factory()
        async with factory() as session:
            medicines = list(
                await session.scalars(
                    select(Medicine).where(Medicine.source_document_id == document.id)
                )
            )
            assert len(medicines) >= 1, "extraction should create medicine rows"
            names = {m.generic_name.lower() for m in medicines}
            assert any("paracetamol" in name or "ibuprofen" in name for name in names)

            interactions = list(
                await session.scalars(
                    select(MedicineInteraction).where(
                        MedicineInteraction.medicine_a_id.in_([m.id for m in medicines])
                    )
                )
            )
            # interaction extraction is best-effort; log what we got
            print(f"medicines={names} interactions={len(interactions)}")
    finally:
        await delete_document(document.id)
