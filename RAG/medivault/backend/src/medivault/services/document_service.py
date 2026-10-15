from uuid import UUID, uuid4

from sqlalchemy import delete, select

from medivault.config import get_settings
from medivault.db.models import Document, DocumentChunk, Medicine, Patient
from medivault.dependencies import get_session_factory
from medivault.ingestion.pipeline import collection_name_for
from medivault.utils.errors import IngestError, NotFoundError
from medivault.vectorstore.chroma import get_collection

_ALLOWED_DOC_TYPES = {"medicine", "patient"}


async def create_document(*, filename: str, doc_type: str, data: bytes) -> Document:
    if doc_type not in _ALLOWED_DOC_TYPES:
        raise IngestError(f"doc_type must be one of {sorted(_ALLOWED_DOC_TYPES)}")
    if not filename.lower().endswith(".pdf"):
        raise IngestError("only .pdf files are supported")
    settings = get_settings()
    if len(data) > settings.max_pdf_bytes:
        raise IngestError("PDF exceeds size limit")
    if not data:
        raise IngestError("empty file")

    document_id = uuid4()
    settings.uploads_path.mkdir(parents=True, exist_ok=True)
    (settings.uploads_path / f"{document_id}.pdf").write_bytes(data)

    factory = get_session_factory()
    async with factory() as session:
        document = Document(id=document_id, doc_type=doc_type, filename=filename)
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document


async def list_documents() -> list[Document]:
    factory = get_session_factory()
    async with factory() as session:
        result = await session.scalars(
            select(Document).order_by(Document.created_at.desc())
        )
        return list(result)


async def get_document(document_id: UUID) -> Document:
    factory = get_session_factory()
    async with factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            raise NotFoundError(f"document {document_id} not found")
        return document


async def delete_document(document_id: UUID) -> None:
    factory = get_session_factory()
    async with factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            raise NotFoundError(f"document {document_id} not found")
        chunk_ids = list(
            await session.scalars(
                select(DocumentChunk.chroma_id).where(
                    DocumentChunk.document_id == document_id
                )
            )
        )
        collection = get_collection(collection_name_for(document.doc_type))
        if chunk_ids:
            collection.delete(ids=chunk_ids)
        await session.execute(
            delete(Medicine).where(Medicine.source_document_id == document_id)
        )
        await session.execute(
            delete(Patient).where(Patient.source_document_id == document_id)
        )
        await session.delete(document)
        await session.commit()

    settings = get_settings()
    file_path = settings.uploads_path / f"{document_id}.pdf"
    if file_path.exists():
        file_path.unlink()
