import tempfile
from pathlib import Path

from fastapi import APIRouter, Request, status
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from ..errors import Conflict, Invalid
from ..schemas import BackupOut, BackupStatusOut
from ..services import backups as svc
from ..services.settings import get_settings

router = APIRouter(prefix="/backups", tags=["backups"])

MAX_UPLOAD = 512 * 1024 * 1024  # far larger than years of factory data


def _out(b: svc.BackupFile) -> BackupOut:
    return BackupOut(name=b.name, size=b.size, created_at=b.created_at, kind=b.kind)


def _copy_dir(request: Request) -> str:
    with request.app.state.session_factory() as session:
        return get_settings(session).backup_copy_dir.strip()


@router.get("", response_model=BackupStatusOut)
def backup_status(request: Request):
    settings = request.app.state.settings
    files = svc.list_backups(settings.data_dir)
    copy_dir = _copy_dir(request)
    return BackupStatusOut(
        backups=[_out(b) for b in files],
        last_backup_at=files[0].created_at if files else None,
        copy_dir=copy_dir,
        copy_dir_ok=Path(copy_dir).is_dir() if copy_dir else None,
        last_error=request.app.state.backup_scheduler.last_error,
    )


@router.post("", response_model=BackupOut, status_code=status.HTTP_201_CREATED)
def back_up_now(request: Request):
    settings = request.app.state.settings
    with request.app.state.backup_scheduler.lock:
        backup = svc.create_backup(
            settings.db_path, settings.data_dir, "manual", _copy_dir(request)
        )
    return _out(backup)


@router.get("/{name}/download")
def download(name: str, request: Request):
    backup = svc.get_backup(request.app.state.settings.data_dir, name)
    return FileResponse(backup.path, filename=backup.name, media_type="application/vnd.sqlite3")


def _restore(request: Request, source: Path) -> BackupOut:
    """Swap in a backup. A copy of the current data is saved first."""
    state = request.app.state
    settings = state.settings
    copy_dir = _copy_dir(request)
    with state.backup_scheduler.lock:
        staged = svc.prepare_restore(source, settings.db_path, settings.data_dir)
        safety = svc.create_backup(settings.db_path, settings.data_dir, "before-restore", copy_dir)
        state.engine.dispose()  # close every connection to the live file
        try:
            svc.swap_in(staged, settings.db_path)
        except PermissionError as exc:  # Windows: the file is still open somewhere
            staged.unlink(missing_ok=True)
            raise Conflict(
                "The data is busy. Close other FMS windows and try again.",
                reason="restore_busy",
            ) from exc
    return _out(safety)


@router.post("/{name}/restore", response_model=BackupOut)
def restore_saved(name: str, request: Request):
    """Restore one of the backups kept on the laptop. Returns the safety copy made first."""
    backup = svc.get_backup(request.app.state.settings.data_dir, name)
    return _restore(request, backup.path)


@router.post("/restore-upload", response_model=BackupOut)
async def restore_upload(request: Request):
    """Restore a backup file sent from this device (e.g. copied back from a USB drive)."""
    with tempfile.NamedTemporaryFile(
        dir=request.app.state.settings.data_dir, suffix=".upload", delete=False
    ) as tmp:
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_UPLOAD:
                tmp.close()
                Path(tmp.name).unlink(missing_ok=True)
                raise Invalid("That file is too large to be an FMS backup", reason="not_a_backup")
            tmp.write(chunk)
    path = Path(tmp.name)
    try:
        return await run_in_threadpool(_restore, request, path)
    finally:
        svc.remove_with_sidecars(path)
