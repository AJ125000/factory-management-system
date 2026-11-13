from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..errors import NotFound
from ..models import WorkerType
from ..schemas import WorkerTypeCreate, WorkerTypeUpdate
from . import audit
from ._common import apply_changes

ENTITY = "worker_type"


def list_worker_types(session: Session, include_inactive: bool = False) -> list[WorkerType]:
    stmt = select(WorkerType).order_by(WorkerType.name_en)
    if not include_inactive:
        stmt = stmt.where(WorkerType.is_active.is_(True))
    return list(session.scalars(stmt))


def get_worker_type(session: Session, worker_type_id: str) -> WorkerType:
    wt = session.get(WorkerType, worker_type_id)
    if wt is None:
        raise NotFound("Worker type not found", worker_type_id=worker_type_id)
    return wt


def _unique_code(session: Session, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:30] or "type"
    code, n = base, 1
    while session.scalar(select(WorkerType.id).where(WorkerType.code == code)):
        n += 1
        code = f"{base}_{n}"
    return code


def create_worker_type(session: Session, data: WorkerTypeCreate) -> WorkerType:
    wt = WorkerType(
        code=_unique_code(session, data.name_en),
        name_en=data.name_en,
        name_hi=data.name_hi or None,
        pay_scheme=data.pay_scheme.value,
    )
    session.add(wt)
    session.flush()
    audit.record(
        session,
        "create",
        ENTITY,
        wt.id,
        f"Added worker type {wt.name_en}",
        after=audit.snapshot(wt),
    )
    return wt


def update_worker_type(session: Session, worker_type_id: str, data: WorkerTypeUpdate) -> WorkerType:
    wt = get_worker_type(session, worker_type_id)
    before = audit.snapshot(wt)
    apply_changes(
        wt,
        data.model_dump(exclude_unset=True),
        required=("name_en", "is_active"),
        blank_to_none=("name_hi",),
    )
    session.flush()
    audit.record(
        session,
        "update",
        ENTITY,
        wt.id,
        f"Edited worker type {wt.name_en}",
        before=before,
        after=audit.snapshot(wt),
    )
    return wt
