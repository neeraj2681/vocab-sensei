from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SettingsDep
from app.api.documents import DocumentResponse, DocumentServiceDep, OwnedDocument
from app.db.models import CurrentReading
from app.db.session import get_session
from app.db.types import utcnow
from app.services.readiness import ReadinessService
from app.services.readings import ReadingError, ReadingService

router = APIRouter(prefix="/readings", tags=["readings"])


class ReadingResponse(BaseModel):
    document: DocumentResponse
    priority: int  # 0 = read first
    current_chapter_index: int
    current_chapter_title: str | None
    current_chapter_readiness: int | None = None  # 0-100, see /documents/{id}/readiness

    @classmethod
    def of(cls, reading: CurrentReading, word_count: int, readiness: int | None = None) -> Self:
        chapters = reading.document.chapters
        index = reading.current_chapter_index
        return cls(
            document=DocumentResponse.of(reading.document, word_count),
            priority=reading.priority,
            current_chapter_index=index,
            current_chapter_title=chapters[index].title if index < len(chapters) else None,
            current_chapter_readiness=readiness,
        )


class StartReadingRequest(BaseModel):
    document_id: int


class SetChapterRequest(BaseModel):
    current_chapter_index: int


class ReorderRequest(BaseModel):
    document_ids: list[int]  # highest priority first


def get_reading_service(session: Annotated[Session, Depends(get_session)]) -> ReadingService:
    return ReadingService(session)


ReadingServiceDep = Annotated[ReadingService, Depends(get_reading_service)]


def get_readiness_service(
    session: Annotated[Session, Depends(get_session)], settings: SettingsDep
) -> ReadinessService:
    return ReadinessService(session, settings.scoring)


ReadinessDep = Annotated[ReadinessService, Depends(get_readiness_service)]


def responses(
    readings: list[CurrentReading], documents: DocumentServiceDep, readiness: ReadinessDep
) -> list[ReadingResponse]:
    counts = documents.word_counts([r.document for r in readings])
    now = utcnow()

    def current(reading: CurrentReading) -> int | None:
        chapters = readiness.for_document(reading.user_id, reading.document, now)
        index = reading.current_chapter_index
        return chapters[index].readiness if index < len(chapters) else None

    return [ReadingResponse.of(r, counts[r.document_id], current(r)) for r in readings]


def current_reading(
    user: CurrentUser, document: OwnedDocument, readings: ReadingServiceDep
) -> CurrentReading:
    reading = readings.get(user.id, document.id)
    if reading is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You're not reading this book")
    return reading


CurrentReadingDep = Annotated[CurrentReading, Depends(current_reading)]


@router.get("")
def list_readings(
    user: CurrentUser,
    readings: ReadingServiceDep,
    documents: DocumentServiceDep,
    readiness: ReadinessDep,
) -> list[ReadingResponse]:
    return responses(readings.list_for(user.id), documents, readiness)


@router.post("", status_code=status.HTTP_201_CREATED)
def start_reading(
    body: StartReadingRequest,
    user: CurrentUser,
    readings: ReadingServiceDep,
    documents: DocumentServiceDep,
    readiness: ReadinessDep,
) -> ReadingResponse:
    document = documents.get_for(user.id, body.document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    try:
        reading = readings.start(user.id, document)
    except ReadingError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    return responses([reading], documents, readiness)[0]


@router.put("/order")
def reorder_readings(
    body: ReorderRequest,
    user: CurrentUser,
    readings: ReadingServiceDep,
    documents: DocumentServiceDep,
    readiness: ReadinessDep,
) -> list[ReadingResponse]:
    try:
        reordered = readings.reorder(user.id, body.document_ids)
    except ReadingError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return responses(reordered, documents, readiness)


@router.patch("/{document_id}")
def set_chapter(
    body: SetChapterRequest,
    reading: CurrentReadingDep,
    readings: ReadingServiceDep,
    documents: DocumentServiceDep,
    readiness: ReadinessDep,
) -> ReadingResponse:
    try:
        readings.set_chapter(reading, body.current_chapter_index)
    except ReadingError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return responses([reading], documents, readiness)[0]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def stop_reading(reading: CurrentReadingDep, readings: ReadingServiceDep) -> None:
    readings.stop(reading)
