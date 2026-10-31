from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Self

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import CurrentUser, DictionaryLoader, SettingsDep, get_dictionary
from app.core.config import Settings
from app.core.enums import DocumentFormat, DocumentStatus, PartOfSpeech
from app.db.models import Document
from app.db.session import get_session, get_session_factory
from app.db.types import utcnow
from app.services.documents import DocumentService, FileTooLargeError, UploadError
from app.services.readiness import ReadinessService
from app.services.words import WordService, definitions_in_context

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
    word_count: int
    classic: bool = False  # a built-in book everyone can read

    @classmethod
    def of(cls, document: Document, word_count: int) -> Self:
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
            word_count=word_count,
            classic=document.is_classic,
        )


class DocumentDetailResponse(DocumentResponse):
    chapters: list[ChapterResponse]

    @classmethod
    def of(cls, document: Document, word_count: int) -> Self:
        summary = DocumentResponse.of(document, word_count).model_dump()
        chapters = [ChapterResponse.model_validate(c) for c in document.chapters]
        return cls(**summary, chapters=chapters)


class DefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pos: str
    text: str


class WordResponse(BaseModel):
    lemma: str
    zipf: float | None
    chapter_index: int
    occurrences: int
    context_sentence: str | None
    pos: PartOfSpeech | None  # how the book uses the word; its definitions come first
    definitions: list[DefinitionResponse]


DictionaryDep = Annotated[DictionaryLoader, Depends(get_dictionary)]


def get_document_service(
    session: Annotated[Session, Depends(get_session)],
    settings: SettingsDep,
    dictionary: DictionaryDep,
) -> DocumentService:
    return DocumentService(session, settings, dictionary)


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]


def process_in_background(
    session_factory: sessionmaker[Session],
    settings: Settings,
    dictionary: DictionaryLoader,
    document_id: int,
) -> None:
    with session_factory() as session:
        DocumentService(session, settings, dictionary).process(document_id)


def readable_document(
    user: CurrentUser, documents: DocumentServiceDep, document_id: int
) -> Document:
    """The user's own book or a built-in classic."""
    document = documents.get_for(user.id, document_id)
    if document is None:  # someone else's document looks exactly like a missing one
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return document


ReadableDocument = Annotated[Document, Depends(readable_document)]


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def upload(
    file: UploadFile,
    user: CurrentUser,
    documents: DocumentServiceDep,
    settings: SettingsDep,
    dictionary: DictionaryDep,
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
    background: BackgroundTasks,
) -> DocumentResponse:
    try:
        document = documents.create(user.id, file.filename or "upload", file.file)
    except FileTooLargeError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(exc)) from None
    except UploadError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from None
    background.add_task(process_in_background, session_factory, settings, dictionary, document.id)
    return DocumentResponse.of(document, word_count=0)


@router.get("")
def list_documents(user: CurrentUser, documents: DocumentServiceDep) -> list[DocumentResponse]:
    owned = documents.list_for(user.id)
    counts = documents.word_counts(owned)
    return [DocumentResponse.of(d, counts[d.id]) for d in owned]


@router.get("/classics")
def list_classics(user: CurrentUser, documents: DocumentServiceDep) -> list[DocumentResponse]:
    """Built-in public-domain books anyone can read, ready to start."""
    classics = [d for d in documents.list_classics() if d.status == DocumentStatus.READY]
    counts = documents.word_counts(classics)
    return [DocumentResponse.of(d, counts[d.id]) for d in classics]


@router.get("/{document_id}")
def get_document(
    document: ReadableDocument, documents: DocumentServiceDep
) -> DocumentDetailResponse:
    return DocumentDetailResponse.of(document, documents.word_counts([document])[document.id])


@router.get("/{document_id}/words")
def list_words(
    document: ReadableDocument,
    session: Annotated[Session, Depends(get_session)],
    chapter: Annotated[int | None, Query(ge=0)] = None,
) -> list[WordResponse]:
    """Learnable words in reading order (where each first appears), optionally for one chapter."""
    return [
        WordResponse(
            lemma=word.lemma,
            zipf=word.zipf_frequency,
            chapter_index=chapter_index,
            occurrences=occurrence.occurrences,
            context_sentence=occurrence.context_sentence,
            pos=occurrence.pos,
            definitions=[
                DefinitionResponse.model_validate(d)
                for d in definitions_in_context(word, occurrence.pos)
            ],
        )
        for occurrence, word, chapter_index in WordService(session).words_for_document(
            document, chapter
        )
    ]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document: ReadableDocument, user: CurrentUser, documents: DocumentServiceDep
) -> None:
    if document.owner_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Built-in classics can't be deleted")
    documents.delete(document)


class ChapterReadinessResponse(BaseModel):
    index: int
    title: str | None
    words: int
    done: int  # learned or known
    in_progress: int
    new: int
    readiness: int  # 0-100: the average progress of the chapter's words


@router.get("/{document_id}/readiness")
def chapter_readiness(
    document: ReadableDocument,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
    settings: SettingsDep,
) -> list[ChapterReadinessResponse]:
    """How ready you are for each chapter."""
    service = ReadinessService(session, settings.scoring)
    return [
        ChapterReadinessResponse(**asdict(c))
        for c in service.for_document(user.id, document, utcnow())
    ]
