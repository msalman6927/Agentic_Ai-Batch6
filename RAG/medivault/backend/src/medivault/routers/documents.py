from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile, status

from medivault.ingestion.pipeline import ingest_document
from medivault.schemas.document import DocumentListOut, DocumentOut
from medivault.services import document_service
from medivault.utils.errors import IngestError

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    doc_type: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> DocumentOut:
    if not file.filename:
        raise IngestError("file has no name")
    data = await file.read()
    document = await document_service.create_document(
        filename=file.filename, doc_type=doc_type, data=data
    )
    background_tasks.add_task(ingest_document, document.id)
    return DocumentOut.model_validate(document)


@router.get("", response_model=DocumentListOut)
async def list_documents() -> DocumentListOut:
    documents = await document_service.list_documents()
    return DocumentListOut(items=[DocumentOut.model_validate(doc) for doc in documents])


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: UUID) -> DocumentOut:
    document = await document_service.get_document(document_id)
    return DocumentOut.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: UUID) -> None:
    await document_service.delete_document(document_id)
