"""Celery tasks. Start a worker with `celery -A app.jobs.celery_app worker`."""

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.dictionary.types import Dictionary
from app.dictionary.wordnet import WordNetDictionary
from app.jobs.celery_app import celery_app
from app.services.documents import DocumentService
from app.services.gutenberg import fetch_and_process


@lru_cache
def _wordnet(data_dir: Path, lexicon: str, senses_per_pos: int) -> Dictionary:
    return WordNetDictionary(data_dir, lexicon, senses_per_pos)  # errors aren't cached: retried


def _dictionary() -> Dictionary:
    settings = get_settings()
    config = settings.dictionary
    return _wordnet(settings.dictionary_dir, config.lexicon, config.senses_per_pos)


@celery_app.task(name="documents.process")  # type: ignore[untyped-decorator]
def process_document(document_id: int) -> None:
    """Extracts a book's words (see DocumentService.process); failures are stored on it."""
    with SessionLocal() as session:
        DocumentService(session, get_settings(), _dictionary).process(document_id)


@celery_app.task(name="documents.fetch_gutenberg")  # type: ignore[untyped-decorator]
def fetch_gutenberg_book(document_id: int) -> None:
    """Downloads a Project Gutenberg book if needed, then processes it like an upload."""
    with SessionLocal() as session:
        fetch_and_process(session, get_settings(), _dictionary, document_id)
