import logging
from datetime import date, datetime
from typing import Annotated, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DictionaryLoader, SettingsDep, get_dictionary
from app.api.documents import DocumentServiceDep
from app.core.enums import QuestionType, WordStatus
from app.core.speech import AudioError, Recognizer
from app.db.models import Question
from app.db.session import get_session
from app.db.types import utcnow
from app.dictionary.types import DictionaryUnavailableError
from app.quiz.speech import said
from app.services.library import LibraryService
from app.services.quiz import (
    AlreadyAnsweredError,
    Focus,
    InvalidChoiceError,
    NoWordsError,
    PractisedWord,
    Preview,
    QuestionNotFoundError,
    QuizService,
    Stats,
    WordNotKnownError,
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
    speaking: Annotated[
        bool, Query(description='the screen can record: "say this word" questions may come')
    ] = False,
) -> QuizService:
    return QuizService(session, settings, dictionary, speaking=speaking)


QuizServiceDep = Annotated[QuizService, Depends(get_quiz_service)]


class OutcomeResponse(BaseModel):
    points: int  # what the live score changes by
    learned: bool  # the word reaches "learned"


class QuestionResponse(BaseModel):
    """What the screen shows, and what it shows after either answer.

    `prompt` is the word (definition_mcq), a meaning (reverse) or the book's sentence with a blank
    (fill_in_blank); for the last two the word itself is the answer. The correct option, the
    word's meaning, the book sentence and both outcomes come along so tapping an option shows the
    whole result at once while the answer saves in the background: a learner who peeks only
    fools themselves.
    """

    id: int
    type: QuestionType
    prompt: str
    options: list[str]
    correct_index: int
    word: str
    meaning: str | None
    context_sentence: str | None
    counted: bool  # False when the word came back too soon to score
    if_right: OutcomeResponse
    if_wrong: OutcomeResponse
    next: "QuestionResponse | None" = None  # with include_next: the one kept ready after it

    @classmethod
    def of(cls, question: Question, preview: Preview) -> Self:
        return cls(
            id=question.id,
            type=question.type,
            prompt=question.prompt,
            options=list(question.options),
            correct_index=question.correct_index,
            word=preview.lemma,
            meaning=preview.meaning,
            context_sentence=preview.sentence,
            counted=preview.counted,
            if_right=OutcomeResponse(
                points=preview.points_if_right, learned=preview.learned_if_right
            ),
            if_wrong=OutcomeResponse(points=preview.points_if_wrong, learned=False),
        )


class DayResponse(BaseModel):
    date: date
    answers: int
    met: bool  # judged by that day's goal, like the streak (or covered by a streak freeze)
    points: int  # net score earned that day
    frozen: bool  # a streak freeze covered it


class StatsResponse(BaseModel):
    total: int
    today: int
    daily_goal: int
    streak: int
    week: list[DayResponse]  # the last seven days, today last
    combo: int  # right answers in a row; Ninja Mode (double coins) from `combo_after`
    combo_after: int
    combo_multiplier: int
    double_coins_until: datetime | None  # the Shop's double coins are running until then
    learned_today: int  # words that reached "learned" today

    @classmethod
    def of(cls, stats: Stats) -> Self:
        return cls(
            total=stats.total,
            today=stats.today,
            daily_goal=stats.daily_goal,
            streak=stats.streak,
            combo=stats.combo,
            combo_after=stats.combo_after,
            combo_multiplier=stats.combo_multiplier,
            double_coins_until=stats.double_coins_until,
            learned_today=stats.learned_today,
            week=[
                DayResponse(
                    date=d.date, answers=d.answers, met=d.met, points=d.points, frozen=d.frozen
                )
                for d in stats.week
            ],
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
    next: QuestionResponse | None  # with include_next: the question now on screen
    after_next: QuestionResponse | None = None  # and the one kept ready after it
    heard: str | None = None  # "say this word": what the speech recogniser heard


class PractisedWordResponse(BaseModel):
    word: str
    book: str | None
    meaning: str | None
    sentence: str | None  # where the book uses it
    progress: int  # 0-100
    learned: bool
    known: bool  # marked "I know this": never asked again
    later: bool  # in progress but waiting its turn (beyond the words practised now)
    also_in: list[str]  # the user's other current reads that use the word

    @classmethod
    def of(cls, word: PractisedWord) -> Self:
        return cls(
            word=word.lemma,
            book=word.book,
            meaning=word.meaning,
            sentence=word.sentence,
            progress=word.progress,
            learned=word.learned,
            known=word.known,
            later=word.later,
            also_in=list(word.also_in),
        )


class HistoryPointResponse(BaseModel):
    number: int
    total: int
    correct: bool
    answered_at: datetime


def get_focus(
    user_id: int, documents: DocumentServiceDep, document_id: int | None, chapter: int | None
) -> Focus | None:
    """'Study this chapter', from the document_id and chapter query parameters."""
    if (document_id is None) != (chapter is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Give both document_id and chapter, or neither"
        )
    if document_id is None or chapter is None:
        return None
    if documents.get_for(user_id, document_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return Focus(document_id, chapter)


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
    include_next: Annotated[
        bool, Query(description="also the question kept ready after it")
    ] = False,
) -> QuestionResponse:
    """The question to show: the unanswered one if there is one, otherwise a new one."""
    focus = get_focus(user.id, documents, document_id, chapter)
    if focus is None:
        LibraryService(session, settings).start_default_if_new(user.id)  # new users get a classic
    try:
        if not include_next:
            question = quiz.current_question(user.id, now, focus)
            return QuestionResponse.of(question, quiz.preview(user.id, question, now))
        current, after = quiz.upcoming(user.id, now, focus)
        response = QuestionResponse.of(current, quiz.preview(user.id, current, now))
        if after is not None:
            response.next = QuestionResponse.of(after, quiz.preview(user.id, after, now))
        return response
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
    documents: DocumentServiceDep,
    now: Now,
    tz: TimeZone,
    include_next: Annotated[
        bool, Query(description="also make and send the next question")
    ] = False,
    document_id: Annotated[
        int | None, Query(description="with `chapter`: study one chapter")
    ] = None,
    chapter: Annotated[int | None, Query(ge=0)] = None,
) -> AnswerResponse:
    """Saves the answer. With include_next, the next question comes along (one round trip
    instead of two); the screen passes its chapter focus so that question fits it."""
    focus = get_focus(user.id, documents, document_id, chapter)
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
        **(next_questions(quiz, user.id, now, focus) if include_next else {"next": None}),
    )


class SpeakRequest(BaseModel):
    heard: Annotated[str, Field(max_length=300)]  # from /pronunciation/transcribe, confirmed


@router.post("/questions/{question_id}/speak")
def speak(
    question_id: int,
    body: SpeakRequest,
    user: CurrentUser,
    quiz: QuizServiceDep,
    documents: DocumentServiceDep,
    now: Now,
    tz: TimeZone,
    include_next: Annotated[bool, Query()] = False,
    document_id: Annotated[int | None, Query()] = None,
    chapter: Annotated[int | None, Query(ge=0)] = None,
) -> AnswerResponse:
    """Answers a "say this word" question with what the speech recogniser heard (the player saw
    it and confirmed it): right when it is the word."""
    try:
        question = quiz.unanswered_question(user.id, question_id)
    except QuestionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except AlreadyAnsweredError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    if question.type is not QuestionType.SAY_WORD:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Not a speaking question")
    response = answer(
        question_id,
        AnswerRequest(chosen_index=0 if said(body.heard, question.prompt) else 1),
        user,
        quiz,
        documents,
        now,
        tz,
        include_next,
        document_id,
        chapter,
    )
    response.heard = body.heard
    return response


@router.post("/questions/{question_id}/skip", status_code=status.HTTP_204_NO_CONTENT)
def skip(question_id: int, user: CurrentUser, quiz: QuizServiceDep, now: Now) -> None:
    """Drops a "say this word" question; none come for the next 10 minutes (can't speak now)."""
    try:
        quiz.skip(user.id, question_id, now)
    except (QuestionNotFoundError, AlreadyAnsweredError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None


def hear(speech: Recognizer, audio: UploadFile, word: str, max_bytes: int) -> str:
    """What the recording says (422 if it isn't readable audio or is too big)."""
    data = audio.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "That recording is too long")
    try:
        return speech.transcribe(data, word)
    except AudioError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


def next_questions(
    quiz: QuizService, user_id: int, now: datetime, focus: Focus | None
) -> dict[str, QuestionResponse | None]:
    """The question now on screen and the one kept ready after it; None when there's nothing
    to ask (the screen then asks itself and shows why)."""
    try:
        current, after = quiz.upcoming(user_id, now, focus)
    except (NoWordsError, DictionaryUnavailableError):
        return {"next": None, "after_next": None}
    return {
        "next": QuestionResponse.of(current, quiz.preview(user_id, current, now)),
        "after_next": (
            QuestionResponse.of(after, quiz.preview(user_id, after, now)) if after else None
        ),
    }


class NextQuestionsResponse(BaseModel):
    next: QuestionResponse | None  # the question now on screen
    after_next: QuestionResponse | None = None  # and the one kept ready after it


@router.post("/questions/{question_id}/know", response_model=None)
def know(
    question_id: int,
    user: CurrentUser,
    quiz: QuizServiceDep,
    documents: DocumentServiceDep,
    now: Now,
    include_next: Annotated[bool, Query(description="also send the next questions")] = False,
    document_id: Annotated[
        int | None, Query(description="with `chapter`: study one chapter")
    ] = None,
    chapter: Annotated[int | None, Query(ge=0)] = None,
) -> Response | NextQuestionsResponse:
    """Marks the word known ("I know this"). With include_next, the next questions come along
    (like an answer); without it, 204 and the screen asks for the next question itself."""
    focus = get_focus(user.id, documents, document_id, chapter)
    try:
        quiz.know(user.id, question_id, now)
    except QuestionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except AlreadyAnsweredError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    if not include_next:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return NextQuestionsResponse(**next_questions(quiz, user.id, now, focus))


@router.get("/stats")
def stats(user: CurrentUser, quiz: QuizServiceDep, now: Now, tz: TimeZone) -> StatsResponse:
    return StatsResponse.of(quiz.stats(user.id, now, tz))


@router.put("/goal")
def set_goal(
    body: GoalRequest, user: CurrentUser, quiz: QuizServiceDep, now: Now, tz: TimeZone
) -> StatsResponse:
    """Changes the daily goal from today on; returns the stats with the new goal."""
    quiz.set_daily_goal(user.id, body.daily_goal, now, tz)
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
def words(
    user: CurrentUser,
    quiz: QuizServiceDep,
    now: Now,
    include_known: Annotated[
        bool, Query(description='also the words marked "I know this"')
    ] = False,
) -> list[PractisedWordResponse]:
    """Words the user has answered, with their progress towards "learned" (progress page).

    Known words only come when asked for: an app cached from before they existed would show
    them as learning at 100%."""
    return [
        PractisedWordResponse.of(w)
        for w in quiz.practised_words(user.id, now)
        if include_known or not w.known
    ]


@router.post("/combo/end", status_code=status.HTTP_204_NO_CONTENT)
def end_combo(user: CurrentUser, quiz: QuizServiceDep) -> None:
    """The player chose to stop after a session: Ninja Mode ends (the screen warned them)."""
    quiz.end_combo(user.id)


@router.post("/words/{lemma}/learn", status_code=status.HTTP_204_NO_CONTENT)
def learn_again(lemma: str, user: CurrentUser, quiz: QuizServiceDep) -> None:
    """Takes a word marked "I know this" back into learning, so the quiz asks it again."""
    try:
        quiz.learn_again(user.id, lemma)
    except WordNotKnownError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
