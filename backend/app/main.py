from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, backup, documents, health, learning, quiz, readings, triage


def create_app() -> FastAPI:
    app = FastAPI(title="Vocab Sensei", version="0.1.0")
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
    return app


app = create_app()
