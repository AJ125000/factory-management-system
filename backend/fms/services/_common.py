from __future__ import annotations

from collections.abc import Iterable
from typing import Any


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
