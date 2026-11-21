from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import GroupBy, ProductionSummaryOut, WagesReportOut
from ..services import reports as svc

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/wages", response_model=WagesReportOut)
def wages(
    start: date,
    end: date,
    worker_id: list[str] | None = Query(default=None),
    machine_id: str | None = None,
    include_entries: bool = False,
    session: Session = Depends(get_session),
):
    """Wages earned per worker between two dates (inclusive)."""
    return svc.wages_report(session, start, end, worker_id, include_entries, machine_id)


@router.get("/production", response_model=ProductionSummaryOut)
def production(
    start: date,
    end: date,
    group_by: GroupBy = "month",
    worker_id: list[str] | None = Query(default=None),
    machine_id: str | None = None,
    session: Session = Depends(get_session),
):
    """Production and wages grouped by day, month or year."""
    return svc.production_summary(session, start, end, group_by, worker_id, machine_id)
