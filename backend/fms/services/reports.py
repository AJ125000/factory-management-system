"""Wages earned and production summaries.

Wages are computed per entry at the rate in effect on that entry's date (see rates.py),
so totals are always consistent with the per-entry breakdown printed on wage slips.
Each operator entry also pays the loader of its machine on that date (see
production.entry_pays), so a loader's wages are the sum of those entries.
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
from ..wages import ZERO, Role
from .machines import LoaderBook
from .production import Pay, entry_pays, to_out
from .rates import RateBook

AREA_PLACES = Decimal("0.01")


def _area(value: Decimal) -> Decimal:
    return value.quantize(AREA_PLACES, rounding=ROUND_HALF_UP)


def check_period(start: date, end: date) -> None:
    if start > end:
        raise Invalid("The start date must be on or before the end date", reason="bad_period")


def entries_in_period(
    session: Session, start: date, end: date, machine_id: str | None = None
) -> list[ProductionEntry]:
    stmt = (
        select(ProductionEntry)
        .where(ProductionEntry.entry_date >= start, ProductionEntry.entry_date <= end)
        .order_by(ProductionEntry.entry_date, ProductionEntry.created_at)
    )
    if machine_id:
        stmt = stmt.where(ProductionEntry.machine_id == machine_id)
    return list(session.scalars(stmt).unique())


def pays_in_period(
    session: Session,
    start: date,
    end: date,
    worker_ids: Sequence[str] | None = None,
    machine_id: str | None = None,
) -> list[tuple[ProductionEntry, list[Pay], int]]:
    """Every entry in the period with the pay of the chosen workers (all, if none chosen).

    The last item counts entries whose machine had no loader (nobody paid for loading).
    """
    check_period(start, end)
    book = RateBook.load(session)
    loaders = LoaderBook.load(session)
    wanted = set(worker_ids or ())
    out = []
    for entry in entries_in_period(session, start, end, machine_id):
        pays = entry_pays(entry, book, loaders)
        no_loader = any(p.worker_id is None for p in pays)
        chosen = [
            p for p in pays if p.worker_id is not None and (not wanted or p.worker_id in wanted)
        ]
        if chosen:
            out.append(
                (entry, chosen, int(no_loader and (not wanted or entry.worker_id in wanted)))
            )
    return out


class _Totals:
    def __init__(self) -> None:
        self.entry_count = 0
        self.quantity = 0
        self.area = Decimal(0)
        self.rft = Decimal(0)
        self.cuts = 0
        self.wage = ZERO
        self.missing = 0

    def add(self, entry: ProductionEntry, wages: list[Decimal | None], rft: bool = True) -> None:
        self.entry_count += 1
        self.quantity += entry.quantity
        self.area += entry.area_sqft
        if rft:  # loaders are paid by sq ft: running ft would mean nothing on their slip
            self.rft += entry.rft_total or 0
        self.cuts += entry.cuts * entry.quantity
        if any(w is None for w in wages):
            self.missing += 1
        self.wage += sum((w for w in wages if w is not None), ZERO)


def wages_report(
    session: Session,
    start: date,
    end: date,
    worker_ids: Sequence[str] | None = None,
    include_entries: bool = False,
    machine_id: str | None = None,
) -> WagesReportOut:
    """Wages earned by each worker paid from entries in the period."""
    rows_by_worker: dict[str, tuple[_Totals, list]] = {}
    book = RateBook.load(session) if include_entries else None
    loaders = LoaderBook.load(session) if include_entries else None
    no_loader = 0
    produced = Decimal(0)
    for entry, pays, missing_loader in pays_in_period(session, start, end, worker_ids, machine_id):
        no_loader += missing_loader
        produced += entry.area_sqft
        for pay in pays:
            assert pay.worker_id is not None
            totals, outs = rows_by_worker.setdefault(pay.worker_id, (_Totals(), []))
            totals.add(entry, [pay.total], rft=pay.role is Role.OPERATOR)
            if include_entries:
                assert book is not None and loaders is not None
                outs.append(to_out(entry, book, loaders, paid_as=pay.role))

    rows: list[WorkerWagesOut] = []
    for worker_id, (totals, outs) in rows_by_worker.items():
        worker = session.get(Worker, worker_id)
        assert worker is not None
        rows.append(
            WorkerWagesOut(
                worker_id=worker_id,
                name_en=worker.name_en,
                name_hi=worker.name_hi,
                worker_type_name_en=worker.worker_type.name_en,
                worker_type_name_hi=worker.worker_type.name_hi,
                role=Role(worker.worker_type.role),
                is_archived=worker.is_archived,
                entry_count=totals.entry_count,
                total_quantity=totals.quantity,
                total_area_sqft=_area(totals.area),
                total_rft=_area(totals.rft),
                total_cuts=totals.cuts,
                total_wage=totals.wage,
                missing_rate_entries=totals.missing,
                entries=outs if include_entries else None,
            )
        )
    rows.sort(key=lambda r: r.name_en.lower())
    return WagesReportOut(
        start=start,
        end=end,
        workers=rows,
        total_wage=sum((r.total_wage for r in rows), ZERO),
        total_area_sqft=_area(produced),  # each entry once, not once per worker paid
        missing_rate_entries=sum(r.missing_rate_entries for r in rows),
        no_loader_entries=no_loader,
    )


def _period_key(d: date, group_by: GroupBy) -> str:
    if group_by == "day":
        return d.isoformat()
    if group_by == "month":
        return f"{d.year:04d}-{d.month:02d}"
    return f"{d.year:04d}"


def _bucket_out(period: str, t: _Totals) -> ProductionBucketOut:
    return ProductionBucketOut(
        period=period,
        entry_count=t.entry_count,
        total_quantity=t.quantity,
        total_area_sqft=_area(t.area),
        total_rft=_area(t.rft),
        total_cuts=t.cuts,
        total_wage=t.wage,
        missing_rate_entries=t.missing,
    )


def production_summary(
    session: Session,
    start: date,
    end: date,
    group_by: GroupBy = "month",
    worker_ids: Sequence[str] | None = None,
    machine_id: str | None = None,
) -> ProductionSummaryOut:
    """Production (and the wages paid for it) per day, month or year.

    Each entry counts once, with the operator's and the loader's pay together.
    Periods with no entries are omitted.
    """
    buckets: dict[str, _Totals] = {}
    totals = _Totals()
    for entry, pays, _ in pays_in_period(session, start, end, worker_ids, machine_id):
        wages = [p.total for p in pays]
        key = _period_key(entry.entry_date, group_by)
        buckets.setdefault(key, _Totals()).add(entry, wages)
        totals.add(entry, wages)
    return ProductionSummaryOut(
        start=start,
        end=end,
        group_by=group_by,
        buckets=[_bucket_out(k, buckets[k]) for k in sorted(buckets)],
        totals=_bucket_out("total", totals),
    )
