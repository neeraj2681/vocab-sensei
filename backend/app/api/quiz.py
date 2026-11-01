import logging
from datetime import date, datetime
from typing import Annotated, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DictionaryLoader, SettingsDep, get_dictionary
from app.api.documents import DocumentServiceDep
from app.core.enums import QuestionType, WordStatus
from app.db.models import Question
from app.db.session import get_session
from app.db.types import utcnow
from app.dictionary.types import DictionaryUnavailableError
from app.services.library import LibraryService
from app.services.quiz import (
    AlreadyAnsweredError,
    Focus,
    InvalidChoiceError,
    NoWordsError,
    PractisedWord,
    QuestionNotFoundError,
    QuizService,
    Stats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quiz", tags=["quiz"])


def get_now() -> datetime:
    """The current time; tests override it to move between days."""
    return utcnow()


def get_timezone(
    tz: Annotated[str, Query(description="IANA name, e.g. Asia/Kolkata")] = "UTC",
) -> ZoneInfo:
    """The user's time zone, which decides when "today" starts for the daily goal.

    Old names (Asia/Calcutta, US/Eastern) work through the tzdata package. A name nobody knows
    falls back to UTC: a quirky browser must never stop someone from answering.
    """
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("unknown time zone %r; counting days in UTC", tz)
        return ZoneInfo("UTC")


Now = Annotated[datetime, Depends(get_now)]
TimeZone = Annotated[ZoneInfo, Depends(get_timezone)]


def get_quiz_service(
    session: Annotated[Session, Depends(get_session)],
    settings: SettingsDep,
    dictionary: Annotated[DictionaryLoader, Depends(get_dictionary)],
) -> QuizService:
    return QuizService(session, settings, dictionary)


QuizServiceDep = Annotated[QuizService, Depends(get_quiz_service)]


class QuestionResponse(BaseModel):
    """What the screen shows. The correct answer is only revealed after answering.

    `prompt` is the word (definition_mcq), a meaning (reverse) or the book's sentence with a blank
    (fill_in_blank); for the last two the word itself is the answer, so it isn't sent.
    """

    id: int
    type: QuestionType
    prompt: str
    options: list[str]

    @classmethod
    def of(cls, question: Question) -> Self:
        return cls(
            id=question.id,
            type=question.type,
            prompt=question.prompt,
            options=list(question.options),
        )


class DayResponse(BaseModel):
    date: date
    answers: int
    met: bool  # judged by that day's goal, like the streak


class StatsResponse(BaseModel):
    total: int
    today: int
    daily_goal: int
    streak: int
    week: list[DayResponse]  # the last seven days, today last

    @classmethod
    def of(cls, stats: Stats) -> Self:
        return cls(
            total=stats.total,
            today=stats.today,
            daily_goal=stats.daily_goal,
            streak=stats.streak,
            week=[DayResponse(date=d.date, answers=d.answers, met=d.met) for d in stats.week],
        )


class GoalRequest(BaseModel):
    daily_goal: int = Field(ge=1, le=200)


class AnswerRequest(BaseModel):
    chosen_index: int


class AnswerResponse(BaseModel):
    correct: bool
    correct_index: int
    points: int  # what the live score changes by: +5, -10, or 0 (asked too soon, or total at 0)
    score_delta: int  # what the word's own score changed by
    counted: bool  # False when the word came back too soon to score
    word: str  # revealed now: reverse and fill-in questions hide it until answered
    meaning: str | None
    word_score: int
    word_status: WordStatus
    context_sentence: str | None  # the sentence from the book, shown after answering
    stats: StatsResponse


class PractisedWordResponse(BaseModel):
    word: str
    book: str | None
    meaning: str | None
    sentence: str | None  # where the book uses it
    progress: int  # 0-100
    learned: bool

    @classmethod
    def of(cls, word: PractisedWord) -> Self:
        return cls(
            word=word.lemma,
            book=word.book,
            meaning=word.meaning,
            sentence=word.sentence,
            progress=word.progress,
            learned=word.learned,
        )


class HistoryPointResponse(BaseModel):
    number: int
    total: int
    correct: bool
    answered_at: datetime


@router.get("/question")
def current_question(
    user: CurrentUser,
    quiz: QuizServiceDep,
    documents: DocumentServiceDep,
    session: Annotated[Session, Depends(get_session)],
    settings: SettingsDep,
    now: Now,
    document_id: Annotated[
        int | None, Query(description="with `chapter`: study one chapter")
    ] = None,
    chapter: Annotated[int | None, Query(ge=0)] = None,
) -> QuestionResponse:
    """The question to show: the unanswered one if there is one, otherwise a new one."""
    focus = None
    if (document_id is None) != (chapter is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Give both document_id and chapter, or neither"
        )
    if document_id is not None and chapter is not None:
        if documents.get_for(user.id, document_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
        focus = Focus(document_id, chapter)
    else:
        LibraryService(session, settings).start_default_if_new(user.id)  # new users get a classic
    try:
        return QuestionResponse.of(quiz.current_question(user.id, now, focus))
    except NoWordsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except DictionaryUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The dictionary isn't installed on the server yet"
        ) from None


@router.post("/questions/{question_id}/answer")
def answer(
    question_id: int,
    body: AnswerRequest,
    user: CurrentUser,
    quiz: QuizServiceDep,
    now: Now,
    tz: TimeZone,
) -> AnswerResponse:
    try:
        outcome = quiz.answer(user.id, question_id, body.chosen_index, now, tz)
    except QuestionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except AlreadyAnsweredError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except InvalidChoiceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return AnswerResponse(
        correct=outcome.correct,
        correct_index=outcome.correct_index,
        points=outcome.points,
        score_delta=outcome.score_delta,
        counted=outcome.counted,
        word=outcome.lemma,
        meaning=outcome.meaning,
        word_score=outcome.word.score,
        word_status=outcome.word.status,
        context_sentence=outcome.question.source_sentence,
        stats=StatsResponse.of(outcome.stats),
    )


@router.post("/questions/{question_id}/know", status_code=status.HTTP_204_NO_CONTENT)
def know(question_id: int, user: CurrentUser, quiz: QuizServiceDep, now: Now) -> None:
    """Marks the word known ("I know this"); fetch the next question afterwards."""
    try:
        quiz.know(user.id, question_id, now)
    except QuestionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except AlreadyAnsweredError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None


@router.get("/stats")
def stats(user: CurrentUser, quiz: QuizServiceDep, now: Now, tz: TimeZone) -> StatsResponse:
    return StatsResponse.of(quiz.stats(user.id, now, tz))


@router.put("/goal")
def set_goal(
    body: GoalRequest, user: CurrentUser, quiz: QuizServiceDep, now: Now, tz: TimeZone
) -> StatsResponse:
    """Changes the daily goal from today on; returns the stats with the new goal."""
    quiz.set_daily_goal(user.id, body.daily_goal, now)
    return StatsResponse.of(quiz.stats(user.id, now, tz))


@router.get("/history")
def history(user: CurrentUser, quiz: QuizServiceDep) -> list[HistoryPointResponse]:
    """Lifetime points after every answer since the first one (for the progress graph)."""
    return [
        HistoryPointResponse(
            number=p.number, total=p.total, correct=p.correct, answered_at=p.answered_at
        )
        for p in quiz.history(user.id)
    ]


@router.get("/words")
def words(user: CurrentUser, quiz: QuizServiceDep, now: Now) -> list[PractisedWordResponse]:
    """Words the user has answered, with their progress towards "learned" (progress page)."""
    return [PractisedWordResponse.of(w) for w in quiz.practised_words(user.id, now)]
