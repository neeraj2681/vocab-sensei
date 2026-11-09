from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DictionaryLoader, get_dictionary
from app.db.session import get_session
from app.quiz.placement import level_name
from app.services.placement import PlacementError, PlacementService

router = APIRouter(prefix="/placement", tags=["placement"])


def get_placement_service(
    session: Annotated[Session, Depends(get_session)],
    dictionary: Annotated[DictionaryLoader, Depends(get_dictionary)],
) -> PlacementService:
    return PlacementService(session, dictionary)


PlacementServiceDep = Annotated[PlacementService, Depends(get_placement_service)]


class CheckResponse(BaseModel):
    words: list[str]  # 20 words in random order: answer "I know it" or not for each


class AnswerRequest(BaseModel):
    word: str = Field(max_length=60)
    known: bool


class SaveRequest(BaseModel):
    answers: list[AnswerRequest] = Field(max_length=40)


class LevelResponse(BaseModel):
    level: float | None  # Zipf where words stop being known; None: not measured yet
    name: str | None  # e.g. "Advanced"


class EasyWordResponse(BaseModel):
    word: str
    meaning: str | None
    book: str


def _level(level: float | None) -> LevelResponse:
    return LevelResponse(level=level, name=level_name(level) if level is not None else None)


@router.get("")
def new_check(user: CurrentUser, placement: PlacementServiceDep) -> CheckResponse:
    """A fresh placement check (about two minutes)."""
    return CheckResponse(words=placement.items())


@router.put("")
def save_check(
    body: SaveRequest, user: CurrentUser, placement: PlacementServiceDep
) -> LevelResponse:
    """Works out the user's word level from their answers; new words easier than it are skipped."""
    try:
        level = placement.save(user.id, [(a.word, a.known) for a in body.answers])
    except PlacementError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return _level(level)


@router.get("/level")
def my_level(user: CurrentUser, placement: PlacementServiceDep) -> LevelResponse:
    return _level(placement.level(user.id))


@router.get("/probably-known")
def probably_known(user: CurrentUser, placement: PlacementServiceDep) -> list[EasyWordResponse]:
    """Words from the books being read that the user's level says they already know (not quizzed;
    POST /quiz/words/{word}/learn takes one into learning)."""
    return [
        EasyWordResponse(word=w.lemma, meaning=w.meaning, book=w.book)
        for w in placement.probably_known(user.id)
    ]
