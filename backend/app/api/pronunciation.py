from typing import Annotated

from fastapi import APIRouter, Form, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SettingsDep, SpeechDep
from app.api.quiz import hear
from app.quiz.speech import said

router = APIRouter(prefix="/pronunciation", tags=["pronunciation"])


class HeardResponse(BaseModel):
    heard: str  # what the speech recogniser heard


class CheckRequest(BaseModel):
    word: Annotated[str, Field(max_length=100)]
    heard: Annotated[str, Field(max_length=300)]  # from /transcribe, confirmed by the player


class PronunciationResponse(BaseModel):
    heard: str
    correct: bool  # close enough to the word


@router.post("/transcribe")
def transcribe(
    word: Annotated[str, Form(max_length=100)],
    audio: UploadFile,
    user: CurrentUser,
    speech: SpeechDep,
    settings: SettingsDep,
) -> HeardResponse:
    """What the recording says (recognised on our server; the audio isn't kept). The screen shows
    it so the player can confirm it, or try again, before it's judged."""
    return HeardResponse(heard=hear(speech, audio, word, settings.speech.max_audio_bytes))


@router.post("")
def check(body: CheckRequest, user: CurrentUser) -> PronunciationResponse:
    """Practice: was what was heard the word?"""
    return PronunciationResponse(heard=body.heard, correct=said(body.heard, body.word))
