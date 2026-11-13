"""Domain errors. The API turns these into JSON error responses."""

from __future__ import annotations

from typing import Any


class FMSError(Exception):
    status_code = 400
    code = "error"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFound(FMSError):
    status_code = 404
    code = "not_found"


class Conflict(FMSError):
    status_code = 409
    code = "conflict"


class Invalid(FMSError):
    status_code = 422
    code = "invalid"
