from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import DeviceSession
from ..schemas import (
    AuthStatusOut,
    DeviceOut,
    LoginIn,
    LoginOut,
    PasswordChangeIn,
    SetupIn,
)
from ..services import auth as svc

router = APIRouter(prefix="/auth", tags=["auth"])


def bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def current_device_id(request: Request) -> str:
    """Set by the login check in main.py for every protected request."""
    return request.state.device_id


def _device_out(device: DeviceSession, current_id: str | None = None) -> DeviceOut:
    out = DeviceOut.model_validate(device)
    out.current = device.id == current_id
    return out


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/status", response_model=AuthStatusOut)
def auth_status(request: Request, session: Session = Depends(get_session)):
    """Public: has the owner password been set, and is this device logged in?"""
    token = bearer_token(request)
    device = svc.device_for_token(session, token) if token else None
    return AuthStatusOut(
        setup_required=svc.setup_required(session),
        logged_in=device is not None,
        device=_device_out(device, device.id) if device else None,
    )


@router.post("/setup", response_model=LoginOut, status_code=status.HTTP_201_CREATED)
def setup(data: SetupIn, session: Session = Depends(get_session)):
    """Public, first run only: set the owner password and log this device in."""
    device, token = svc.setup_owner(session, data.password, data.device_name)
    session.commit()
    return LoginOut(token=token, device=_device_out(device, device.id))


@router.post("/login", response_model=LoginOut)
def login(data: LoginIn, request: Request, session: Session = Depends(get_session)):
    throttle: svc.LoginThrottle = request.app.state.login_throttle
    client = _client(request)
    with throttle.lock:
        throttle.check(client)
        try:
            device, token = svc.login(session, data.password, data.device_name)
        except svc.Unauthorized:
            throttle.failed(client)
            raise
        throttle.succeeded(client)
        session.commit()
    return LoginOut(token=token, device=_device_out(device, device.id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, session: Session = Depends(get_session)):
    svc.sign_out(session, current_device_id(request))
    session.commit()


@router.get("/devices", response_model=list[DeviceOut])
def devices(request: Request, session: Session = Depends(get_session)):
    current = current_device_id(request)
    return [_device_out(d, current) for d in svc.list_devices(session)]


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def sign_out_device(device_id: str, session: Session = Depends(get_session)):
    """Sign a device out (e.g. a lost phone). It must log in again with the password."""
    svc.sign_out(session, device_id)
    session.commit()


@router.post("/password")
def change_password(
    data: PasswordChangeIn, request: Request, session: Session = Depends(get_session)
) -> dict[str, int]:
    signed_out = svc.change_password(
        session,
        data.current_password,
        data.new_password,
        current_device_id(request),
        data.sign_out_other_devices,
    )
    session.commit()
    return {"signed_out_devices": signed_out}
