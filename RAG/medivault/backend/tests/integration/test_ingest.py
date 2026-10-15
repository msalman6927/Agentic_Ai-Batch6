import asyncio

import pytest
from sqlalchemy import text

from medivault.db.models import Document
from medivault.dependencies import get_session_factory
from medivault.ingestion.pipeline import ingest_document
from medivault.services.document_service import create_document, delete_document
from medivault.vectorstore.chroma import get_collection
from medivault.vectorstore.collections import MEDICINE_CHUNKS, META_DOCUMENT_ID
from tests.integration.pdf_factory import make_minimal_pdf

SAMPLE_TEXT = (
    "Paracetamol 500mg tablet. Indications: fever, mild pain. "
    "Dosage: one tablet every six hours. Max 4g per day."
)


async def _wait_indexed(document_id, max_wait_seconds: float = 90.0) -> Document:
    factory = get_session_factory()
    deadline = asyncio.get_running_loop().time() + max_wait_seconds
    while True:
        async with factory() as session:
            document = await session.get(Document, document_id)
            assert document is not None
            if document.status in {"indexed", "failed"}:
                return document
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f"document stuck in status={document.status}")
        await asyncio.sleep(1.0)


@pytest.mark.integration
async def test_full_ingest_dual_write() -> None:
    document = await create_document(
        filename="medicines.pdf",
        doc_type="medicine",
        data=make_minimal_pdf(SAMPLE_TEXT),
    )
    try:
        await ingest_document(document.id)
        document = await _wait_indexed(document.id)
        assert document.status == "indexed", document.error
        assert document.chunk_count and document.chunk_count >= 1

        factory = get_session_factory()
        async with factory() as session:
            chunks = (
                await session.execute(
                    text(
                        "SELECT content FROM document_chunks "
                        "WHERE document_id = :doc_id "
                        "AND tsv @@ plainto_tsquery('simple', 'paracetamol')"
                    ),
                    {"doc_id": document.id},
                )
            ).fetchall()
        assert chunks, "FTS should match the ingested chunk"

        collection = get_collection(MEDICINE_CHUNKS)
        count = collection.get(where={META_DOCUMENT_ID: str(document.id)})["ids"]
        assert len(count) == document.chunk_count
    finally:
        await delete_document(document.id)
        collection = get_collection(MEDICINE_CHUNKS)
        remaining = collection.get(where={META_DOCUMENT_ID: str(document.id)})["ids"]
        assert remaining == []


@pytest.mark.integration
async def test_delete_removes_chunks() -> None:
    document = await create_document(
        filename="p.pdf",
        doc_type="patient",
        data=make_minimal_pdf("Patient Ali, age 45"),
    )
    await ingest_document(document.id)
    document = await _wait_indexed(document.id)
    assert document.status == "indexed", document.error
    await delete_document(document.id)
    factory = get_session_factory()
    async with factory() as session:
        remaining = (
            await session.execute(
                text("SELECT count(*) FROM document_chunks WHERE document_id = :d"),
                {"d": document.id},
            )
        ).scalar()
    assert remaining == 0
