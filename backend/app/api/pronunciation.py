from typing import Annotated

from fastapi import APIRouter, Form, UploadFile
from pydantic import BaseModel

from app.api.deps import CurrentUser, SettingsDep, SpeechDep
from app.api.quiz import hear
from app.quiz.speech import said

router = APIRouter(prefix="/pronunciation", tags=["pronunciation"])


class PronunciationResponse(BaseModel):
    heard: str  # what the speech recogniser heard
    correct: bool  # close enough to the word


@router.post("")
def check(
    word: Annotated[str, Form(max_length=100)],
    audio: UploadFile,
    user: CurrentUser,
    speech: SpeechDep,
    settings: SettingsDep,
) -> PronunciationResponse:
    """Practice: did the recording say `word`? Recognised on our server; the audio isn't kept."""
    heard = hear(speech, audio, word, settings.speech.max_audio_bytes)
    return PronunciationResponse(heard=heard, correct=said(heard, word))
