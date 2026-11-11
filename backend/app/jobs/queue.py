"""Where the API sends background work: a Celery worker, or its own process in development."""

from collections.abc import Callable
from typing import Protocol

from fastapi import BackgroundTasks


class JobQueue(Protocol):
    def process_document(self, document_id: int) -> None: ...
    def fetch_gutenberg_book(self, document_id: int) -> None: ...


class CeleryJobQueue:
    def process_document(self, document_id: int) -> None:
        from app.jobs import tasks  # deferred: importing tasks builds the Celery app

        tasks.process_document.delay(document_id)

    def fetch_gutenberg_book(self, document_id: int) -> None:
        from app.jobs import tasks

        tasks.fetch_gutenberg_book.delay(document_id)


class BackgroundJobQueue:
    """Runs jobs in the API process after the response (development and tests)."""

    def __init__(
        self,
        background: BackgroundTasks,
        run: Callable[[int], None],
        run_gutenberg: Callable[[int], None],
    ) -> None:
        self._background = background
        self._run = run
        self._run_gutenberg = run_gutenberg

    def process_document(self, document_id: int) -> None:
        self._background.add_task(self._run, document_id)

    def fetch_gutenberg_book(self, document_id: int) -> None:
        self._background.add_task(self._run_gutenberg, document_id)
