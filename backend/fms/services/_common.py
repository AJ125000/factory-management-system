from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..errors import Gone
from ..models import Tombstone


def apply_changes(
    obj: Any,
    changes: dict[str, Any],
    *,
    required: Iterable[str] = (),
    blank_to_none: Iterable[str] = (),
) -> None:
    """Apply a PATCH-style dict of changes.

    * `required` fields ignore an explicit null ("leave unchanged").
    * `blank_to_none` fields store "" as NULL.
    """
    required, blank_to_none = set(required), set(blank_to_none)
    for field, value in changes.items():
        if value is None and field in required:
            continue
        if value == "" and field in blank_to_none:
            value = None
        setattr(obj, field, value)


def existing_replay[T](
    session: Session, model: type[T], record_id: object, entity: str
) -> T | None:
    """The record a device already created with this id, if any.

    Devices create records with their own ids and may send the same change twice
    (e.g. the connection dropped before they saw the reply). A repeat is answered with
    the existing record instead of creating a duplicate or failing - and if the record
    has since been deleted (say on the laptop), the repeat must not bring it back.
    """
    if record_id is None:
        return None
    if existing := session.get(model, str(record_id)):
        return existing
    deleted = session.scalar(
        select(Tombstone.id).where(
            Tombstone.entity == entity, Tombstone.entity_id == str(record_id)
        )
    )
    if deleted:
        raise Gone("This was deleted on another device", reason="deleted", id=str(record_id))
    return None
