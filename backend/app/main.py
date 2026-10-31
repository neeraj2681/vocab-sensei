import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, backup, documents, health, learning, quiz, readings, reminders, triage
from app.core.config import get_settings
from app.core.email import SmtpEmailSender
from app.core.push import WebPushSender, load_or_create_keys
from app.db.session import SessionLocal
from app.services.reminders import run_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Runs the daily-reminder check in a background thread while the app is up."""
    settings = get_settings()
    if not settings.reminders.scheduler_enabled:
        yield
        return
    stop = threading.Event()
    push = WebPushSender(
        load_or_create_keys(settings.push, settings.data_dir), settings.push.subject
    )
    thread = threading.Thread(
        target=run_scheduler,
        args=(stop, SessionLocal, settings, SmtpEmailSender(settings.email), push),
        name="reminders",
        daemon=True,
    )
    thread.start()
    yield
    stop.set()
    thread.join(timeout=5)


def create_app() -> FastAPI:
    app = FastAPI(title="Vocab Sensei", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],  # Vite dev server
        allow_credentials=True,  # send the session cookie
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(readings.router, prefix="/api")
    app.include_router(learning.router, prefix="/api")
    app.include_router(quiz.router, prefix="/api")
    app.include_router(triage.router, prefix="/api")
    app.include_router(backup.router, prefix="/api")
    app.include_router(reminders.router, prefix="/api")
    return app


app = create_app()
