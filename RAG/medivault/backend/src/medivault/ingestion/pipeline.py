import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from chromadb.api.types import Metadata
from sqlalchemy import delete, select

from medivault.config import get_settings
from medivault.db.models import Document, DocumentChunk
from medivault.dependencies import get_session_factory
from medivault.ingestion.chunker import chunk_pages
from medivault.ingestion.extractor import extract_medicines, extract_patients
from medivault.ingestion.pdf_loader import load_pdf_pages
from medivault.llm.embeddings import embed_texts
from medivault.services.medicine_service import replace_medicines_for_document
from medivault.services.patient_service import replace_patients_for_document
from medivault.vectorstore.chroma import get_collection
from medivault.vectorstore.collections import (
    MEDICINE_CHUNKS,
    META_CHUNK_INDEX,
    META_DOC_TYPE,
    META_DOCUMENT_ID,
    PATIENT_CHUNKS,
)

logger = logging.getLogger(__name__)

_COLLECTION_BY_DOC_TYPE = {
    "medicine": MEDICINE_CHUNKS,
    "patient": PATIENT_CHUNKS,
}


def collection_name_for(doc_type: str) -> str:
    return _COLLECTION_BY_DOC_TYPE.get(doc_type, MEDICINE_CHUNKS)


async def ingest_document(document_id: UUID) -> None:
    """Background worker: parse PDF, chunk, embed, dual-write Chroma + Postgres."""
    factory = get_session_factory()
    async with factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            logger.warning("document %s vanished before ingest", document_id)
            return
        document.status = "processing"
        await session.commit()

    try:
        settings = get_settings()
        file_path = settings.uploads_path / f"{document_id}.pdf"
        data = file_path.read_bytes()
        pages = load_pdf_pages(data)
        chunks = chunk_pages(
            pages,
            doc_type=document.doc_type,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )
        vectors = await embed_texts(chunks)

        collection = get_collection(collection_name_for(document.doc_type))
        async with factory() as session:
            existing = await session.scalars(
                select(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )
            old_ids = [chunk.chroma_id for chunk in existing]
            if old_ids:
                collection.delete(ids=old_ids)
                await session.execute(
                    delete(DocumentChunk).where(
                        DocumentChunk.document_id == document_id
                    )
                )

            chunk_rows: list[DocumentChunk] = []
            chroma_ids: list[str] = []
            chroma_docs: list[str] = []
            chroma_meta: list[Metadata] = []
            chroma_vectors: list[Sequence[float]] = []

            pairs = zip(chunks, vectors, strict=True)
            for index, (content, vector) in enumerate(pairs):
                chroma_id = str(uuid4())
                row = DocumentChunk(
                    document_id=document_id,
                    chunk_index=index,
                    content=content,
                    meta={
                        "doc_type": document.doc_type,
                        "filename": document.filename,
                    },
                    chroma_id=chroma_id,
                )
                chunk_rows.append(row)
                chroma_ids.append(chroma_id)
                chroma_docs.append(content)
                chroma_meta.append(
                    {
                        META_DOCUMENT_ID: str(document_id),
                        META_CHUNK_INDEX: index,
                        META_DOC_TYPE: document.doc_type,
                    }
                )
                chroma_vectors.append(vector)

            if chroma_ids:
                collection.upsert(
                    ids=chroma_ids,
                    documents=chroma_docs,
                    metadatas=chroma_meta,
                    embeddings=chroma_vectors,
                )
            session.add_all(chunk_rows)

            fresh = await session.get(Document, document_id)
            if fresh is None:  # pragma: no cover - defensive
                return
            fresh.status = "indexed"
            fresh.page_count = len(pages)
            fresh.chunk_count = len(chunks)
            fresh.error = None
            fresh.indexed_at = datetime.now(UTC)
            await session.commit()

        await _run_extraction(document, chunks)
        logger.info("document %s indexed (%d chunks)", document_id, len(chunks))
    except Exception as exc:  # noqa: BLE001
        logger.exception("ingest failed for %s", document_id)
        async with factory() as session:
            failed = await session.get(Document, document_id)
            if failed is not None:
                failed.status = "failed"
                failed.error = f"{type(exc).__name__}: {exc}"[:2000]
                await session.commit()


async def _run_extraction(document: Document, chunks: list[str]) -> None:
    """Best-effort structured extraction into medicines/patients (+ graph edges)."""
    if not chunks:
        return
    full_text = "\n\n".join(chunks)
    if document.doc_type == "medicine":
        medicine_entries = await extract_medicines(full_text)
        if medicine_entries:
            count = await replace_medicines_for_document(document.id, medicine_entries)
            logger.info("extracted %d medicines for doc %s", count, document.id)
    elif document.doc_type == "patient":
        patient_entries = await extract_patients(full_text)
        if patient_entries:
            count = await replace_patients_for_document(document.id, patient_entries)
            logger.info("extracted %d patients for doc %s", count, document.id)
