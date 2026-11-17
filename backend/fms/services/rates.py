"""Wage rates with effective dates.

A rate applies from its `effective_from` date until the next rate for the same
worker type and component. A production entry is always paid at the rate that was
in effect on its own date, so raising rates never changes wages already earned.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..errors import Conflict, Invalid, NotFound
from ..models import Rate
from ..schemas import RateCreate, RateUpdate
from ..wages import SCHEME_COMPONENTS, PayScheme, RateComponent
from . import audit
from ._common import apply_changes, existing_replay
from .worker_types import get_worker_type

ENTITY = "rate"


class RateBook:
    """In-memory index of all rates for fast "rate on date X" lookups."""

    def __init__(self, rates: Iterable[Rate]) -> None:
        grouped: dict[tuple[str, str], list[tuple[date, Decimal]]] = defaultdict(list)
        for r in rates:
            grouped[(r.worker_type_id, r.component)].append((r.effective_from, r.rate_per_sqft))
        self._dates: dict[tuple[str, str], list[date]] = {}
        self._values: dict[tuple[str, str], list[Decimal]] = {}
        for key, items in grouped.items():
            items.sort(key=lambda item: item[0])
            self._dates[key] = [d for d, _ in items]
            self._values[key] = [v for _, v in items]

    @classmethod
    def load(cls, session: Session) -> RateBook:
        return cls(session.scalars(select(Rate)).unique())

    def lookup_with_date(
        self, worker_type_id: str, component: RateComponent | str, on: date
    ) -> tuple[Decimal, date] | None:
        key = (worker_type_id, str(component))
        dates = self._dates.get(key)
        if not dates:
            return None
        i = bisect_right(dates, on) - 1
        return (self._values[key][i], dates[i]) if i >= 0 else None

    def lookup(
        self, worker_type_id: str, component: RateComponent | str, on: date
    ) -> Decimal | None:
        found = self.lookup_with_date(worker_type_id, component, on)
        return found[0] if found else None

    def rates_for(
        self, worker_type_id: str, scheme: PayScheme | str, on: date
    ) -> dict[RateComponent, Decimal | None]:
        return {c: self.lookup(worker_type_id, c, on) for c in SCHEME_COMPONENTS[PayScheme(scheme)]}


def list_rates(session: Session, worker_type_id: str | None = None) -> list[Rate]:
    stmt = select(Rate).order_by(Rate.worker_type_id, Rate.component, Rate.effective_from.desc())
    if worker_type_id:
        stmt = stmt.where(Rate.worker_type_id == worker_type_id)
    return list(session.scalars(stmt).unique())


def get_rate(session: Session, rate_id: str) -> Rate:
    rate = session.get(Rate, rate_id)
    if rate is None:
        raise NotFound("Rate not found", rate_id=rate_id)
    return rate


def _flush_unique(session: Session) -> None:
    try:
        with session.begin_nested():
            session.flush()
    except IntegrityError as exc:
        raise Conflict(
            "A rate for this worker type and component already starts on that date. "
            "Edit that rate instead.",
            reason="duplicate_effective_date",
        ) from exc


def create_rate(session: Session, data: RateCreate) -> Rate:
    if replay := existing_replay(session, Rate, data.id, ENTITY):
        return replay
    try:
        wt = get_worker_type(session, data.worker_type_id)
    except NotFound as exc:
        raise Invalid(
            "Unknown worker type", reason="unknown_worker_type", worker_type_id=data.worker_type_id
        ) from exc
    allowed = SCHEME_COMPONENTS[PayScheme(wt.pay_scheme)]
    if data.component not in allowed:
        raise Invalid(
            f"{wt.name_en} is paid by {', '.join(allowed)}, not {data.component}",
            reason="component_not_allowed",
            allowed_components=[str(c) for c in allowed],
        )
    rate = Rate(
        **({"id": str(data.id)} if data.id else {}),
        worker_type_id=wt.id,
        component=data.component.value,
        rate_per_sqft=data.rate_per_sqft,
        effective_from=data.effective_from,
        note=data.note or None,
    )
    session.add(rate)
    _flush_unique(session)
    audit.record(
        session,
        "create",
        ENTITY,
        rate.id,
        f"Set {wt.name_en} {rate.component} rate to {rate.rate_per_sqft}/sq ft "
        f"from {rate.effective_from.isoformat()}",
        after=audit.snapshot(rate),
    )
    return rate


def update_rate(session: Session, rate_id: str, data: RateUpdate) -> Rate:
    """Correct a rate. This deliberately recalculates wages for the period it covers."""
    rate = get_rate(session, rate_id)
    before = audit.snapshot(rate)
    apply_changes(
        rate,
        data.model_dump(exclude_unset=True),
        required=("rate_per_sqft", "effective_from"),
        blank_to_none=("note",),
    )
    _flush_unique(session)
    audit.record(
        session,
        "update",
        ENTITY,
        rate.id,
        f"Corrected {rate.component} rate",
        before=before,
        after=audit.snapshot(rate),
    )
    return rate


def delete_rate(session: Session, rate_id: str) -> None:
    rate = get_rate(session, rate_id)
    audit.record(
        session,
        "delete",
        ENTITY,
        rate.id,
        f"Deleted {rate.component} rate",
        before=audit.snapshot(rate),
    )
    audit.tombstone(session, ENTITY, rate.id)
    session.delete(rate)
    session.flush()
