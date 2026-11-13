from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session


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


def existing_replay[T](session: Session, model: type[T], record_id: object) -> T | None:
    """The record a device already created with this id, if any.

    Devices create records with their own ids and may send the same change twice
    (e.g. the connection dropped before they saw the reply). A repeat is answered with
    the existing record instead of creating a duplicate or failing.
    """
    if record_id is None:
        return None
    return session.get(model, str(record_id))
