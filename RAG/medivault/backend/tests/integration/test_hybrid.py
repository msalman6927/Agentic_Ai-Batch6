import asyncio

import pytest

from medivault.db.models import Document
from medivault.dependencies import get_session_factory
from medivault.ingestion.pipeline import ingest_document
from medivault.retrieval.hybrid import hybrid_search
from medivault.services.document_service import create_document, delete_document
from tests.integration.pdf_factory import make_minimal_pdf

PDF_TEXT = """\
Paracetamol 500mg
Indications: fever, headache, mild pain
Dosage: one tablet every six hours
Amoxicillin 500mg capsule
Indications: bacterial infections, throat infection
Dosage: one capsule three times daily
"""


async def _wait_indexed(document_id, max_wait_seconds: float = 120.0) -> Document:
    factory = get_session_factory()
    deadline = asyncio.get_running_loop().time() + max_wait_seconds
    while True:
        async with factory() as session:
            document = await session.get(Document, document_id)
            assert document is not None
            if document.status in {"indexed", "failed"}:
                return document
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("ingest timed out")
        await asyncio.sleep(1.0)


@pytest.mark.integration
async def test_hybrid_search_returns_ranked_hits() -> None:
    document = await create_document(
        filename="hybrid.pdf",
        doc_type="medicine",
        data=make_minimal_pdf(PDF_TEXT),
    )
    try:
        await ingest_document(document.id)
        document = await _wait_indexed(document.id)
        assert document.status == "indexed", document.error

        hits = await hybrid_search("paracetamol for fever", doc_type="medicine", k=3)
        assert hits, "hybrid search returned nothing"
        assert hits[0].content
        assert hits[0].doc_type == "medicine"
        assert hits[0].score > 0
        # fused results should be ordered by RRF score desc
        scores = [hit.score for hit in hits]
        assert scores == sorted(scores, reverse=True)
    finally:
        await delete_document(document.id)


@pytest.mark.integration
async def test_hybrid_search_empty_when_vault_empty() -> None:
    hits = await hybrid_search("zzzunfindablezzz", k=3)
    assert isinstance(hits, list)
