"""Edit history and deletion tombstones."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog, Base, Tombstone


def snapshot(obj: Base) -> dict[str, Any]:
    """All column values of a row, as JSON-friendly values."""
    out: dict[str, Any] = {}
    for col in obj.__table__.columns:
        value = getattr(obj, col.key)
        if isinstance(value, Decimal):
            value = str(value)
        elif isinstance(value, date | datetime):
            value = value.isoformat()
        out[col.key] = value
    return out


def _dump(data: Any) -> str | None:
    return None if data is None else json.dumps(data, ensure_ascii=False, sort_keys=True)


def record(
    session: Session,
    action: str,
    entity: str,
    entity_id: str,
    summary: str,
    before: Any = None,
    after: Any = None,
) -> None:
    session.add(
        AuditLog(
            action=action,
            entity=entity,
            entity_id=entity_id,
            summary=summary,
            before=_dump(before),
            after=_dump(after),
        )
    )


def tombstone(session: Session, entity: str, entity_id: str) -> None:
    session.add(Tombstone(entity=entity, entity_id=entity_id))
