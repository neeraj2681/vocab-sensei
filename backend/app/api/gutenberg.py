import threading
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import CurrentUser, SettingsDep
from app.services.catalogue import (
    Catalogue,
    CatalogueUnavailableError,
    catalogue_path,
    is_stale,
    refresh_catalogue,
)

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
            {"detail": "The book catalogue is being prepared. Try again in a minute."},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            background=background,
        )
    return [CatalogueBookResponse(**vars(book)) for book in books]
