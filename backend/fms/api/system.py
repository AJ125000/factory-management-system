from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import __version__, tailscale
from ..db import get_session
from ..services.settings import get_settings

router = APIRouter(tags=["system"])


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
