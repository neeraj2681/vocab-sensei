from datetime import datetime
from typing import Annotated, Self

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import CurrentUser, SettingsDep
from app.core.config import Settings
from app.core.enums import DocumentFormat, DocumentStatus
from app.db.models import Document
from app.db.session import get_session, get_session_factory
from app.services.documents import DocumentService, FileTooLargeError, UploadError

router = APIRouter(prefix="/documents", tags=["documents"])


class ChapterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    index: int
    title: str | None


class DocumentResponse(BaseModel):
    id: int
    title: str
    author: str | None
    original_filename: str
    format: DocumentFormat
    status: DocumentStatus
    error: str | None
    uploaded_at: datetime
    chapter_count: int

    @classmethod
    def of(cls, document: Document) -> Self:
        return cls(
            id=document.id,
            title=document.title,
            author=document.author,
            original_filename=document.original_filename,
            format=document.format,
            status=document.status,
            error=document.error,
            uploaded_at=document.uploaded_at,
            chapter_count=len(document.chapters),
        )


class DocumentDetailResponse(DocumentResponse):
    chapters: list[ChapterResponse]

    @classmethod
    def of(cls, document: Document) -> Self:
        summary = DocumentResponse.of(document).model_dump()
        chapters = [ChapterResponse.model_validate(c) for c in document.chapters]
        return cls(**summary, chapters=chapters)


def get_document_service(
    session: Annotated[Session, Depends(get_session)], settings: SettingsDep
) -> DocumentService:
    return DocumentService(session, settings)


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]


def process_in_background(
    session_factory: sessionmaker[Session], settings: Settings, document_id: int
) -> None:
    with session_factory() as session:
        DocumentService(session, settings).process(document_id)


def owned_document(user: CurrentUser, documents: DocumentServiceDep, document_id: int) -> Document:
    document = documents.get_for(user.id, document_id)
    if document is None:  # someone else's document looks exactly like a missing one
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return document


OwnedDocument = Annotated[Document, Depends(owned_document)]


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def upload(
    file: UploadFile,
    user: CurrentUser,
    documents: DocumentServiceDep,
    settings: SettingsDep,
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
    background: BackgroundTasks,
) -> DocumentResponse:
    try:
        document = documents.create(user.id, file.filename or "upload", file.file)
    except FileTooLargeError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(exc)) from None
    except UploadError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from None
    background.add_task(process_in_background, session_factory, settings, document.id)
    return DocumentResponse.of(document)


@router.get("")
def list_documents(user: CurrentUser, documents: DocumentServiceDep) -> list[DocumentResponse]:
    return [DocumentResponse.of(d) for d in documents.list_for(user.id)]


@router.get("/{document_id}")
def get_document(document: OwnedDocument) -> DocumentDetailResponse:
    return DocumentDetailResponse.of(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document: OwnedDocument, documents: DocumentServiceDep) -> None:
    documents.delete(document)
