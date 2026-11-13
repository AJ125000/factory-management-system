from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..errors import Conflict, Invalid, NotFound
from ..models import ProductionEntry, Worker
from ..schemas import ProductionCreate, ProductionOut, ProductionUpdate, WageLineOut
from ..util import today
from ..wages import MissingRateError, RateComponent, StoneEntry, WageResult, calculate_wage
from . import audit
from ._common import apply_changes
from .rates import RateBook

ENTITY = "production_entry"


# ------------------------------------------------------------------ wages
def entry_wage(
    entry: ProductionEntry, book: RateBook
) -> tuple[WageResult | None, list[RateComponent]]:
    """The wage for one entry at the rates in effect on its date, or the missing components."""
    scheme = entry.worker_type.pay_scheme
    rates = book.rates_for(entry.worker_type_id, scheme, entry.entry_date)
    stone = StoneEntry(entry.length_ft, entry.width_ft, entry.cuts, entry.quantity)
    try:
        return calculate_wage(scheme, stone, rates), []
    except MissingRateError as exc:
        return None, exc.components


def to_out(entry: ProductionEntry, book: RateBook) -> ProductionOut:
    result, missing = entry_wage(entry, book)
    out = ProductionOut.model_validate(entry)
    out.missing_rates = missing
    if result is not None:
        out.wage = result.total
        out.wage_lines = [
            WageLineOut(
                component=line.component,
                effective_area_sqft=line.effective_area,
                rate_per_sqft=line.rate,
                amount=line.amount,
            )
            for line in result.lines
        ]
    return out


# ------------------------------------------------------------------ queries
def list_entries(
    session: Session,
    start: date | None = None,
    end: date | None = None,
    worker_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, list[ProductionEntry]]:
    conditions = []
    if start:
        conditions.append(ProductionEntry.entry_date >= start)
    if end:
        conditions.append(ProductionEntry.entry_date <= end)
    if worker_id:
        conditions.append(ProductionEntry.worker_id == worker_id)
    total = session.scalar(select(func.count()).select_from(ProductionEntry).where(*conditions))
    stmt = (
        select(ProductionEntry)
        .where(*conditions)
        .order_by(ProductionEntry.entry_date.desc(), ProductionEntry.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return total or 0, list(session.scalars(stmt).unique())


def get_entry(session: Session, entry_id: str) -> ProductionEntry:
    entry = session.get(ProductionEntry, entry_id)
    if entry is None:
        raise NotFound("Production entry not found", entry_id=entry_id)
    return entry


# ------------------------------------------------------------------ changes
def _usable_worker(session: Session, worker_id: str) -> Worker:
    worker = session.get(Worker, worker_id)
    if worker is None:
        raise Invalid("Unknown worker", worker_id=worker_id)
    if worker.is_archived:
        raise Conflict(
            "This worker is archived. Restore them before adding production.",
            reason="worker_archived",
        )
    return worker


def _check_date(entry_date: date) -> None:
    if entry_date > today():
        raise Invalid("The entry date can't be in the future", entry_date=entry_date.isoformat())


def create_entry(session: Session, data: ProductionCreate) -> ProductionEntry:
    worker = _usable_worker(session, data.worker_id)
    _check_date(data.entry_date)
    entry = ProductionEntry(worker_type_id=worker.worker_type_id)
    apply_changes(entry, data.model_dump(), blank_to_none=("notes",))
    session.add(entry)
    session.flush()
    session.refresh(entry)
    audit.record(
        session,
        "create",
        ENTITY,
        entry.id,
        f"Added production for {worker.name_en} on {entry.entry_date.isoformat()}",
        after=audit.snapshot(entry),
    )
    return entry


def update_entry(session: Session, entry_id: str, data: ProductionUpdate) -> ProductionEntry:
    entry = get_entry(session, entry_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("worker_id") and changes["worker_id"] != entry.worker_id:
        worker = _usable_worker(session, changes["worker_id"])
        entry.worker_type_id = worker.worker_type_id
    if changes.get("entry_date"):
        _check_date(changes["entry_date"])

    before = audit.snapshot(entry)
    apply_changes(
        entry,
        changes,
        required=("worker_id", "entry_date", "length_ft", "width_ft", "cuts", "quantity"),
        blank_to_none=("notes",),
    )
    session.flush()
    session.refresh(entry)
    audit.record(
        session,
        "update",
        ENTITY,
        entry.id,
        f"Edited production for {entry.worker.name_en} on {entry.entry_date.isoformat()}",
        before=before,
        after=audit.snapshot(entry),
    )
    return entry


def delete_entry(session: Session, entry_id: str) -> None:
    entry = get_entry(session, entry_id)
    audit.record(
        session,
        "delete",
        ENTITY,
        entry.id,
        f"Deleted production for {entry.worker.name_en} on {entry.entry_date.isoformat()}",
        before=audit.snapshot(entry),
    )
    audit.tombstone(session, ENTITY, entry.id)
    session.delete(entry)
    session.flush()
