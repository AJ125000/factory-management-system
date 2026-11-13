"""Owner preferences, stored as one JSON value per key in app_settings."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AppSetting
from ..schemas import AppSettingsOut, AppSettingsUpdate
from . import audit


def get_settings(session: Session) -> AppSettingsOut:
    stored = {row.key: json.loads(row.value) for row in session.scalars(select(AppSetting))}
    known = {k: v for k, v in stored.items() if k in AppSettingsOut.model_fields}
    return AppSettingsOut(**known)


def update_settings(session: Session, data: AppSettingsUpdate) -> AppSettingsOut:
    before = get_settings(session).model_dump()
    for key, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        row = session.get(AppSetting, key)
        encoded = json.dumps(value, ensure_ascii=False)
        if row is None:
            session.add(AppSetting(key=key, value=encoded))
        else:
            row.value = encoded
    session.flush()
    after = get_settings(session)
    audit.record(
        session,
        "update",
        "settings",
        "app",
        "Changed settings",
        before=before,
        after=after.model_dump(),
    )
    return after
