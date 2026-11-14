import logging
import time
from collections import deque

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import __version__, tailscale
from ..db import get_session
from ..services.settings import get_settings

router = APIRouter(tags=["system"])
client_log = logging.getLogger("fms.client")


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ok", "version": __version__}


class ConnectInfo(BaseModel):
    tailscale_installed: bool
    tailscale_running: bool
    detected_url: str | None
    phone_url: str | None  # what the QR code shows: the owner's override, else detected
    hub_port: int


@router.get("/connect-info", response_model=ConnectInfo)
def connect_info(request: Request, session: Session = Depends(get_session)):
    """Where phones should connect to reach this hub."""
    info = tailscale.detect()
    override = get_settings(session).phone_url.strip()
    return ConnectInfo(
        tailscale_installed=info.installed,
        tailscale_running=info.running,
        detected_url=info.url,
        phone_url=override or info.url,
        hub_port=request.app.state.settings.port,
    )


class SystemInfo(BaseModel):
    version: str
    data_dir: str
    log_file: str
    database_size: int


@router.get("/system-info", response_model=SystemInfo)
def system_info(request: Request):
    """For Settings > About: what's running and where its files are (helps support)."""
    settings = request.app.state.settings
    db = settings.db_path
    return SystemInfo(
        version=__version__,
        data_dir=str(settings.data_dir),
        log_file=str(settings.log_dir / "fms.log"),
        database_size=db.stat().st_size if db.exists() else 0,
    )


class ClientError(BaseModel):
    message: str = Field(max_length=2000)
    stack: str | None = Field(default=None, max_length=8000)
    url: str | None = Field(default=None, max_length=500)
    app_version: str | None = Field(default=None, max_length=40)
    where: str | None = Field(default=None, max_length=100)


_recent: deque[float] = deque(maxlen=60)


@router.post("/client-errors", status_code=status.HTTP_204_NO_CONTENT)
def report_client_error(report: ClientError, request: Request) -> None:
    """Errors from the app on any device end up in the laptop's log, in one place."""
    now = time.monotonic()
    if len(_recent) == _recent.maxlen and now - _recent[0] < 60:
        return  # a broken screen in a loop must not flood the log
    _recent.append(now)
    client_log.warning(
        "App error on %s (app %s, %s): %s\n%s",
        getattr(request.state, "device_id", "?"),
        report.app_version or "?",
        report.url or report.where or "?",
        report.message,
        report.stack or "",
    )
