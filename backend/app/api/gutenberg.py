import threading
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, JobQueueDep, SettingsDep
from app.api.documents import DocumentResponse
from app.db.session import get_session
from app.services.catalogue import (
    Catalogue,
    CatalogueUnavailableError,
    catalogue_path,
    is_stale,
    refresh_catalogue,
)
from app.services.gutenberg import DailyLimitError, GutenbergService, NotInCatalogueError

router = APIRouter(prefix="/library/gutenberg", tags=["library"])

_refresh_lock = threading.Lock()


class CatalogueBookResponse(BaseModel):
    gutenberg_id: int
    title: str
    authors: str


def _refresh_once(path: Path) -> None:
    """Refreshes the catalogue unless another refresh is already running in this process."""
    if not _refresh_lock.acquire(blocking=False):
        return
    try:
        refresh_catalogue(path)
    finally:
        _refresh_lock.release()


@router.get("", response_model=list[CatalogueBookResponse])
def search_gutenberg(
    _user: CurrentUser,
    settings: SettingsDep,
    background: BackgroundTasks,
    q: Annotated[str, Query(max_length=100)] = "",
) -> list[CatalogueBookResponse] | JSONResponse:
    path = catalogue_path(settings.data_dir)
    if is_stale(path):
        background.add_task(_refresh_once, path)
    try:
        books = Catalogue(path).search(q, limit=20)
    except CatalogueUnavailableError:
        # Not an HTTPException: those skip the background task that downloads the catalogue.
        return JSONResponse(
            {"detail": _CATALOGUE_PREPARING},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            background=background,
        )
    return [CatalogueBookResponse(**vars(book)) for book in books]


_CATALOGUE_PREPARING = "The book catalogue is being prepared. Try again in a minute."


@router.post(
    "/{gutenberg_id}", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentResponse
)
def add_gutenberg_book(
    gutenberg_id: int,
    user: CurrentUser,
    settings: SettingsDep,
    session: Annotated[Session, Depends(get_session)],
    background: BackgroundTasks,
    jobs: JobQueueDep,
) -> DocumentResponse | JSONResponse:
    """Puts a Project Gutenberg book on the reader's shelf, fetching it if it's new to us."""
    path = catalogue_path(settings.data_dir)
    if is_stale(path):
        background.add_task(_refresh_once, path)
    service = GutenbergService(session, settings, Catalogue(path))
    try:
        document, fetch = service.add_to_shelf(user.id, gutenberg_id)
    except CatalogueUnavailableError:
        return JSONResponse(
            {"detail": _CATALOGUE_PREPARING},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            background=background,
        )
    except NotInCatalogueError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "That book isn't in Project Gutenberg's catalogue"
        ) from None
    except DailyLimitError:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "You can add one new book a day. Books other readers have added are always free.",
        ) from None
    if fetch:
        jobs.fetch_gutenberg_book(document.id)
    return DocumentResponse.of(document, word_count=0).model_copy(
        update={"classic": True, "gutenberg": True}
    )


@router.delete("/{document_id}/shelf", status_code=status.HTTP_204_NO_CONTENT)
def remove_gutenberg_book(
    document_id: int,
    user: CurrentUser,
    settings: SettingsDep,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """Takes a book off the reader's shelf; the shared book stays for everyone else."""
    GutenbergService(
        session, settings, Catalogue(catalogue_path(settings.data_dir))
    ).remove_from_shelf(user.id, document_id)
