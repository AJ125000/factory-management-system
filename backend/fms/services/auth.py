"""Owner login and device sessions.

- One owner password, stored as a salted scrypt hash (Python's standard library).
- Each device that logs in gets a long random token. The device keeps the token; the
  hub keeps only its SHA-256 hash, so a copy of the database can't be used to log in.
- Devices stay signed in until the owner signs them out (phones may be offline for
  weeks). Changing or resetting the password can sign out every other device.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass, field

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..errors import Conflict, FMSError, Invalid, NotFound
from ..models import DeviceSession, OwnerAccount
from ..util import utcnow
from . import audit

MIN_PASSWORD_LENGTH = 6
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1


class Unauthorized(FMSError):
    status_code = 401
    code = "unauthorized"


class TooManyAttempts(FMSError):
    status_code = 429
    code = "too_many_attempts"


# ------------------------------------------------------------------ passwords
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32
    )
    b64 = base64.b64encode
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${b64(salt).decode()}${b64(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(
            password.encode(),
            salt=base64.b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def _check_new_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise Invalid(
            f"The password must be at least {MIN_PASSWORD_LENGTH} characters",
            reason="password_too_short",
        )


# ------------------------------------------------------------------ tokens
def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def owner(session: Session) -> OwnerAccount | None:
    return session.get(OwnerAccount, 1)


def setup_required(session: Session) -> bool:
    return owner(session) is None


def _new_device(session: Session, name: str) -> tuple[DeviceSession, str]:
    token = secrets.token_urlsafe(32)
    device = DeviceSession(name=name.strip()[:80] or "Device", token_hash=_token_hash(token))
    session.add(device)
    session.flush()
    return device, token


def setup_owner(session: Session, password: str, device_name: str) -> tuple[DeviceSession, str]:
    """First run: set the owner password and log this device in."""
    if not setup_required(session):
        raise Conflict("The owner password is already set", reason="already_set_up")
    _check_new_password(password)
    session.add(OwnerAccount(id=1, password_hash=hash_password(password)))
    device, token = _new_device(session, device_name)
    audit.record(session, "create", "owner", "1", "Set the owner password")
    audit.record(session, "login", "device", device.id, f"Logged in on {device.name}")
    return device, token


def login(session: Session, password: str, device_name: str) -> tuple[DeviceSession, str]:
    account = owner(session)
    if account is None:
        raise Conflict("Set the owner password first", reason="setup_required")
    if not verify_password(password, account.password_hash):
        raise Unauthorized("Wrong password", reason="wrong_password")
    device, token = _new_device(session, device_name)
    audit.record(session, "login", "device", device.id, f"Logged in on {device.name}")
    return device, token


def device_for_token(session: Session, token: str) -> DeviceSession | None:
    device = session.scalar(
        select(DeviceSession).where(DeviceSession.token_hash == _token_hash(token))
    )
    if device is None or device.revoked_at is not None:
        return None
    return device


def touch(session: Session, device: DeviceSession) -> None:
    """Note when a device was last used (at most every few minutes, to avoid writes)."""
    now = utcnow()
    if (now - device.last_seen_at).total_seconds() > 300:
        device.last_seen_at = now
        session.commit()


def list_devices(session: Session) -> list[DeviceSession]:
    return list(
        session.scalars(
            select(DeviceSession)
            .where(DeviceSession.revoked_at.is_(None))
            .order_by(DeviceSession.last_seen_at.desc())
        )
    )


def sign_out(session: Session, device_id: str) -> None:
    device = session.get(DeviceSession, device_id)
    if device is None or device.revoked_at is not None:
        raise NotFound("Device not found", device_id=device_id)
    device.revoked_at = utcnow()
    audit.record(session, "logout", "device", device.id, f"Signed out {device.name}")


def sign_out_all(session: Session, except_device_id: str | None = None) -> int:
    stmt = update(DeviceSession).where(DeviceSession.revoked_at.is_(None))
    if except_device_id:
        stmt = stmt.where(DeviceSession.id != except_device_id)
    result = session.execute(stmt.values(revoked_at=utcnow()))
    return result.rowcount or 0


def change_password(
    session: Session,
    current: str,
    new: str,
    current_device_id: str,
    sign_out_others: bool,
) -> int:
    account = owner(session)
    if account is None or not verify_password(current, account.password_hash):
        raise Unauthorized("The current password is wrong", reason="wrong_password")
    _check_new_password(new)
    account.password_hash = hash_password(new)
    signed_out = sign_out_all(session, except_device_id=current_device_id) if sign_out_others else 0
    audit.record(session, "update", "owner", "1", "Changed the owner password")
    return signed_out


def reset_password(session: Session, new: str) -> int:
    """For the laptop's 'Reset FMS password': sets a new password, signs out every device."""
    _check_new_password(new)
    account = owner(session)
    if account is None:
        session.add(OwnerAccount(id=1, password_hash=hash_password(new)))
    else:
        account.password_hash = hash_password(new)
    signed_out = sign_out_all(session)
    audit.record(session, "update", "owner", "1", "Reset the owner password on the laptop")
    return signed_out


# ------------------------------------------------------------------ guessing
@dataclass
class LoginThrottle:
    """Slows down password guessing: after 5 wrong tries, wait 30 s, doubling to 15 min."""

    free_attempts: int = 5
    base_delay: float = 30.0
    max_delay: float = 900.0
    _failures: dict[str, tuple[int, float]] = field(default_factory=dict)
    # Logins take turns: otherwise many guesses sent at once all pass check() before
    # any failure is recorded, and the limit does nothing.
    lock: threading.Lock = field(default_factory=threading.Lock)

    def check(self, client: str) -> None:
        count, last = self._failures.get(client, (0, 0.0))
        if count < self.free_attempts:
            return
        wait = min(self.base_delay * 2 ** (count - self.free_attempts), self.max_delay)
        remaining = last + wait - time.monotonic()
        if remaining > 0:
            raise TooManyAttempts(
                "Too many wrong passwords. Please wait and try again.",
                reason="too_many_attempts",
                retry_after_seconds=int(remaining) + 1,
            )

    def failed(self, client: str) -> None:
        count, _ = self._failures.get(client, (0, 0.0))
        self._failures[client] = (count + 1, time.monotonic())

    def succeeded(self, client: str) -> None:
        self._failures.pop(client, None)
