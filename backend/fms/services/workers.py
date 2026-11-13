from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..errors import Conflict, Invalid, NotFound
from ..models import ProductionEntry, Worker
from ..schemas import WorkerCreate, WorkerUpdate
from ..util import utcnow
from . import audit
from ._common import apply_changes, existing_replay
from .worker_types import get_worker_type

ENTITY = "worker"


def list_workers(
    session: Session, include_archived: bool = False, search: str | None = None
) -> list[Worker]:
    stmt = select(Worker).order_by(func.lower(Worker.name_en))
    if not include_archived:
        stmt = stmt.where(Worker.archived_at.is_(None))
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(Worker.name_en.ilike(like) | Worker.name_hi.like(like))
    return list(session.scalars(stmt).unique())


def get_worker(session: Session, worker_id: str) -> Worker:
    worker = session.get(Worker, worker_id)
    if worker is None:
        raise NotFound("Worker not found", worker_id=worker_id)
    return worker


def _check_type_usable(session: Session, worker_type_id: str) -> None:
    try:
        wt = get_worker_type(session, worker_type_id)
    except NotFound as exc:
        raise Invalid(
            "Unknown worker type", reason="unknown_worker_type", worker_type_id=worker_type_id
        ) from exc
    if not wt.is_active:
        raise Invalid(
            "This worker type is no longer in use",
            reason="worker_type_inactive",
            worker_type_id=worker_type_id,
        )


def _check_duplicate_name(session: Session, name: str, exclude_id: str | None = None) -> None:
    """Guard against adding the same person twice (e.g. a double tap on the phone)."""
    stmt = select(Worker.id).where(
        func.lower(Worker.name_en) == name.lower(), Worker.archived_at.is_(None)
    )
    if exclude_id:
        stmt = stmt.where(Worker.id != exclude_id)
    existing = session.scalar(stmt)
    if existing:
        raise Conflict(
            "A worker with this name already exists. Add them anyway?",
            reason="duplicate_name",
            existing_worker_id=existing,
        )


def create_worker(session: Session, data: WorkerCreate) -> Worker:
    if replay := existing_replay(session, Worker, data.id):
        return replay
    _check_type_usable(session, data.worker_type_id)
    if not data.allow_duplicate_name:
        _check_duplicate_name(session, data.name_en)
    worker = Worker(id=str(data.id)) if data.id else Worker()
    apply_changes(
        worker,
        data.model_dump(exclude={"allow_duplicate_name", "id"}),
        blank_to_none=("name_hi", "phone", "notes"),
    )
    session.add(worker)
    session.flush()
    audit.record(
        session,
        "create",
        ENTITY,
        worker.id,
        f"Added worker {worker.name_en}",
        after=audit.snapshot(worker),
    )
    return worker


def update_worker(session: Session, worker_id: str, data: WorkerUpdate) -> Worker:
    worker = get_worker(session, worker_id)
    changes = data.model_dump(exclude_unset=True, exclude={"allow_duplicate_name"})
    if changes.get("worker_type_id") and changes["worker_type_id"] != worker.worker_type_id:
        # Past entries keep the type they were paid under; only new entries use the new type.
        _check_type_usable(session, changes["worker_type_id"])
    new_name = changes.get("name_en")
    if new_name and new_name.lower() != worker.name_en.lower() and not data.allow_duplicate_name:
        _check_duplicate_name(session, new_name, exclude_id=worker.id)

    before = audit.snapshot(worker)
    apply_changes(
        worker,
        changes,
        required=("name_en", "worker_type_id"),
        blank_to_none=("name_hi", "phone", "notes"),
    )
    session.flush()
    session.refresh(worker)  # reload the worker_type relationship if it changed
    audit.record(
        session,
        "update",
        ENTITY,
        worker.id,
        f"Edited worker {worker.name_en}",
        before=before,
        after=audit.snapshot(worker),
    )
    return worker


def archive_worker(session: Session, worker_id: str) -> Worker:
    worker = get_worker(session, worker_id)
    if worker.archived_at is None:
        worker.archived_at = utcnow()
        session.flush()
        audit.record(session, "archive", ENTITY, worker.id, f"Archived worker {worker.name_en}")
    return worker


def restore_worker(session: Session, worker_id: str) -> Worker:
    worker = get_worker(session, worker_id)
    if worker.archived_at is not None:
        _check_duplicate_name(session, worker.name_en, exclude_id=worker.id)
        worker.archived_at = None
        session.flush()
        audit.record(session, "restore", ENTITY, worker.id, f"Restored worker {worker.name_en}")
    return worker


def count_entries(session: Session, worker_id: str) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(ProductionEntry)
            .where(ProductionEntry.worker_id == worker_id)
        )
        or 0
    )


def delete_worker(session: Session, worker_id: str, confirm_entries: int) -> int:
    """Permanently delete a worker and all their production entries.

    `confirm_entries` must equal the number of entries that will be deleted - it proves
    the owner saw the real impact (and that no entries were added since they looked).
    The full data is kept in the audit log, so a mistaken delete can be recovered.
    """
    worker = get_worker(session, worker_id)
    entries = list(
        session.scalars(select(ProductionEntry).where(ProductionEntry.worker_id == worker_id))
    )
    if confirm_entries != len(entries):
        raise Conflict(
            "The number of production entries has changed. Please review and confirm again.",
            reason="confirmation_mismatch",
            production_entries=len(entries),
        )

    audit.record(
        session,
        "delete",
        ENTITY,
        worker.id,
        f"Deleted worker {worker.name_en} and {len(entries)} production entries",
        before={
            "worker": audit.snapshot(worker),
            "production_entries": [audit.snapshot(e) for e in entries],
        },
    )
    for entry in entries:
        audit.tombstone(session, "production_entry", entry.id)
    audit.tombstone(session, ENTITY, worker.id)

    session.execute(delete(ProductionEntry).where(ProductionEntry.worker_id == worker_id))
    session.delete(worker)
    session.flush()
    return len(entries)
