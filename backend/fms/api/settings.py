from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import AppSettingsOut, AppSettingsUpdate
from ..services import settings as svc

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=AppSettingsOut)
def get_settings(session: Session = Depends(get_session)):
    return svc.get_settings(session)


@router.patch("", response_model=AppSettingsOut)
def update_settings(data: AppSettingsUpdate, session: Session = Depends(get_session)):
    result = svc.update_settings(session, data)
    session.commit()
    return result
