from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SettingsDep
from app.api.documents import ReadableDocument
from app.core.enums import PartOfSpeech, WordStatus
from app.db.session import get_session
from app.scoring.rules import Triage
from app.services.readings import ReadingService
from app.services.triage import AlreadyQuizzedError, NotInLibraryError, TriageService
from app.services.words import definitions_in_context

router = APIRouter(tags=["sorting"])


def get_triage_service(
    session: Annotated[Session, Depends(get_session)], settings: SettingsDep
) -> TriageService:
    return TriageService(session, settings)


TriageServiceDep = Annotated[TriageService, Depends(get_triage_service)]


class UnsortedWordResponse(BaseModel):
    word_id: int
    lemma: str
    pos: PartOfSpeech | None
    definition: str | None  # the first meaning for how the book uses the word
    context_sentence: str | None
    chapter_index: int
    chapter_title: str | None
    earlier: bool  # from a chapter before the one being read


class SortBatchResponse(BaseModel):
    remaining: int
    from_chapter: int
    words: list[UnsortedWordResponse]


class SortRequest(BaseModel):
    choice: Triage


class SortResponse(BaseModel):
    word_id: int
    status: WordStatus
    score: int


@router.get("/documents/{document_id}/sort")
def next_to_sort(
    document: ReadableDocument,
    user: CurrentUser,
    triage: TriageServiceDep,
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=0, le=100)] = 20,
) -> SortBatchResponse:
    """The book's next unsorted words from the chapter you're reading, 1 in 4 from earlier ones."""
    reading = ReadingService(session).get(user.id, document.id)
    batch = triage.next_batch(user.id, document, reading, limit)
    words = []
    for item in batch.words:
        meanings = definitions_in_context(item.word, item.occurrence.pos)
        words.append(
            UnsortedWordResponse(
                word_id=item.word.id,
                lemma=item.word.lemma,
                pos=item.occurrence.pos,
                definition=meanings[0].text if meanings else None,
                context_sentence=item.occurrence.context_sentence,
                chapter_index=item.chapter.index,
                chapter_title=item.chapter.title,
                earlier=item.earlier,
            )
        )
    return SortBatchResponse(
        remaining=batch.remaining, from_chapter=batch.from_chapter, words=words
    )


@router.put("/words/{word_id}/sort")
def sort_word(
    word_id: int, body: SortRequest, user: CurrentUser, triage: TriageServiceDep
) -> SortResponse:
    """Known (never quizzed), Unsure (starts at 50) or New (starts at 0)."""
    try:
        word = triage.sort(user.id, word_id, body.choice)
    except NotInLibraryError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except AlreadyQuizzedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    return SortResponse(word_id=word.word_id, status=word.status, score=word.score)


@router.delete("/words/{word_id}/sort", status_code=status.HTTP_204_NO_CONTENT)
def undo_sort(word_id: int, user: CurrentUser, triage: TriageServiceDep) -> None:
    """Undo: the word is unsorted again."""
    try:
        triage.undo(user.id, word_id)
    except NotInLibraryError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except AlreadyQuizzedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
