"""Speech recognition on our own server: faster-whisper (MIT) with an English Whisper model.
Audio never leaves the server. The model loads on first use and stays in memory."""

import io
import threading
from pathlib import Path
from typing import Protocol

import av
import numpy as np
from numpy.typing import NDArray

from app.core.config import Settings

SAMPLE_RATE = 16_000
MAX_SECONDS = 8


class AudioError(Exception):
    """The upload isn't audio we can read (or is too long)."""


class Recognizer(Protocol):
    def transcribe(self, audio: bytes, hint: str) -> str: ...


def decode(data: bytes) -> NDArray[np.float32]:
    """Any browser recording (WebM/Opus, MP4/AAC, WAV…) as 16 kHz mono samples."""
    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    chunks: list[NDArray[np.generic]] = []
    try:
        with av.open(io.BytesIO(data), mode="r") as container:
            for frame in container.decode(audio=0):
                chunks += [out.to_ndarray().reshape(-1) for out in resampler.resample(frame)]
            chunks += [out.to_ndarray().reshape(-1) for out in resampler.resample(None)]
    except (av.error.FFmpegError, ValueError, IndexError) as exc:
        raise AudioError("That recording couldn't be read") from exc
    if not chunks:
        raise AudioError("The recording is empty")
    samples = np.concatenate(chunks)[: SAMPLE_RATE * MAX_SECONDS]
    return samples.astype(np.float32) / 32768.0


class WhisperRecognizer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model: object | None = None
        self._lock = threading.Lock()

    def transcribe(self, audio: bytes, hint: str) -> str:
        """What was said, nudged towards `hint` (the word being practised)."""
        samples = decode(audio)
        segments, _ = self._load().transcribe(  # type: ignore[attr-defined]
            samples,
            language="en",
            beam_size=1,
            initial_prompt=f"The word is {hint}.",
            without_timestamps=True,
        )
        return " ".join(segment.text for segment in segments).strip()

    def _load(self) -> object:
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel  # slow to import; only when needed

                speech = self._settings.speech
                where = speech.model_dir or self._settings.data_dir / "whisper"
                path: str | Path = where if (where / "model.bin").is_file() else speech.model
                self._model = WhisperModel(
                    str(path), device="cpu", compute_type="int8", download_root=str(where)
                )
            return self._model


_shared: WhisperRecognizer | None = None


def get_recognizer(settings: Settings) -> WhisperRecognizer:
    global _shared
    if _shared is None:
        _shared = WhisperRecognizer(settings)
    return _shared
