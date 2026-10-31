from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.db.session import get_session
from app.services.backup import Backup, BackupService, BackupVersionError, RestoreSummary

router = APIRouter(prefix="/backup", tags=["backup"])


def get_backup_service(session: Annotated[Session, Depends(get_session)]) -> BackupService:
    return BackupService(session)


BackupServiceDep = Annotated[BackupService, Depends(get_backup_service)]


@router.get("")
def export_backup(user: CurrentUser, backups: BackupServiceDep, response: Response) -> Backup:
    """Your progress as a JSON file (the browser downloads it)."""
    backup = backups.export(user.id)
    name = f"vocab-sensei-backup-{backup.exported_at:%Y-%m-%d}.json"
    response.headers["Content-Disposition"] = f'attachment; filename="{name}"'
    return backup


@router.post("")
def restore_backup(body: Backup, user: CurrentUser, backups: BackupServiceDep) -> RestoreSummary:
    """Merges a backup into your account; progress you already have is kept."""
    try:
        return backups.restore(user.id, body)
    except BackupVersionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
