"""Wages earned and production summaries.

Wages are computed per entry at the rate in effect on that entry's date (see rates.py),
so totals are always consistent with the per-entry breakdown printed on wage slips.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..errors import Invalid
from ..models import ProductionEntry, Worker
from ..schemas import (
    GroupBy,
    ProductionBucketOut,
    ProductionSummaryOut,
    WagesReportOut,
    WorkerWagesOut,
)
from ..wages import ZERO
from .production import entry_wage, to_out
from .rates import RateBook

AREA_PLACES = Decimal("0.01")


def _area(value: Decimal) -> Decimal:
    return value.quantize(AREA_PLACES, rounding=ROUND_HALF_UP)


def check_period(start: date, end: date) -> None:
    if start > end:
        raise Invalid("The start date must be on or before the end date", reason="bad_period")


def entries_in_period(
    session: Session, start: date, end: date, worker_ids: Sequence[str] | None
) -> list[ProductionEntry]:
    stmt = (
        select(ProductionEntry)
        .where(ProductionEntry.entry_date >= start, ProductionEntry.entry_date <= end)
        .order_by(ProductionEntry.entry_date, ProductionEntry.created_at)
    )
    if worker_ids:
        stmt = stmt.where(ProductionEntry.worker_id.in_(worker_ids))
    return list(session.scalars(stmt).unique())


def wages_report(
    session: Session,
    start: date,
    end: date,
    worker_ids: Sequence[str] | None = None,
    include_entries: bool = False,
) -> WagesReportOut:
    """Wages earned by each worker who has production in the period."""
    check_period(start, end)
    book = RateBook.load(session)
    by_worker: dict[str, list[ProductionEntry]] = {}
    for entry in entries_in_period(session, start, end, worker_ids):
        by_worker.setdefault(entry.worker_id, []).append(entry)

    rows: list[WorkerWagesOut] = []
    for worker_id, entries in by_worker.items():
        worker: Worker = entries[0].worker
        total_wage, area, missing = ZERO, Decimal(0), 0
        outs = []
        for entry in entries:
            result, _ = entry_wage(entry, book)
            if result is None:
                missing += 1
            else:
                total_wage += result.total
            area += entry.area_sqft
            if include_entries:
                outs.append(to_out(entry, book))
        rows.append(
            WorkerWagesOut(
                worker_id=worker_id,
                name_en=worker.name_en,
                name_hi=worker.name_hi,
                worker_type_name_en=worker.worker_type.name_en,
                worker_type_name_hi=worker.worker_type.name_hi,
                is_archived=worker.is_archived,
                entry_count=len(entries),
                total_quantity=sum(e.quantity for e in entries),
                total_area_sqft=_area(area),
                total_cuts=sum(e.cuts * e.quantity for e in entries),
                total_wage=total_wage,
                missing_rate_entries=missing,
                entries=outs if include_entries else None,
            )
        )
    rows.sort(key=lambda r: r.name_en.lower())
    return WagesReportOut(
        start=start,
        end=end,
        workers=rows,
        total_wage=sum((r.total_wage for r in rows), ZERO),
        total_area_sqft=_area(sum((r.total_area_sqft for r in rows), Decimal(0))),
        missing_rate_entries=sum(r.missing_rate_entries for r in rows),
    )


def _period_key(d: date, group_by: GroupBy) -> str:
    if group_by == "day":
        return d.isoformat()
    if group_by == "month":
        return f"{d.year:04d}-{d.month:02d}"
    return f"{d.year:04d}"


class _Bucket:
    def __init__(self, period: str) -> None:
        self.period = period
        self.entry_count = 0
        self.quantity = 0
        self.area = Decimal(0)
        self.cuts = 0
        self.wage = ZERO
        self.missing = 0

    def add(self, entry: ProductionEntry, wage: Decimal | None) -> None:
        self.entry_count += 1
        self.quantity += entry.quantity
        self.area += entry.area_sqft
        self.cuts += entry.cuts * entry.quantity
        if wage is None:
            self.missing += 1
        else:
            self.wage += wage

    def out(self) -> ProductionBucketOut:
        return ProductionBucketOut(
            period=self.period,
            entry_count=self.entry_count,
            total_quantity=self.quantity,
            total_area_sqft=_area(self.area),
            total_cuts=self.cuts,
            total_wage=self.wage,
            missing_rate_entries=self.missing,
        )


def production_summary(
    session: Session,
    start: date,
    end: date,
    group_by: GroupBy = "month",
    worker_ids: Sequence[str] | None = None,
) -> ProductionSummaryOut:
    """Production (and wages) per day, month or year. Periods with no entries are omitted."""
    check_period(start, end)
    book = RateBook.load(session)
    buckets: dict[str, _Bucket] = {}
    totals = _Bucket("total")
    for entry in entries_in_period(session, start, end, worker_ids):
        result, _ = entry_wage(entry, book)
        wage = result.total if result else None
        key = _period_key(entry.entry_date, group_by)
        buckets.setdefault(key, _Bucket(key)).add(entry, wage)
        totals.add(entry, wage)
    return ProductionSummaryOut(
        start=start,
        end=end,
        group_by=group_by,
        buckets=[buckets[k].out() for k in sorted(buckets)],
        totals=totals.out(),
    )
