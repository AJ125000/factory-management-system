from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import GroupBy, Language
from ..services import exports as svc
from ..services.reports import check_period

router = APIRouter(prefix="/exports", tags=["exports"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _download(data: bytes, filename: str) -> Response:
    return Response(
        content=data,
        media_type=XLSX,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/wages.xlsx")
def wages_xlsx(
    start: date,
    end: date,
    lang: Language = "en",
    worker_id: list[str] | None = Query(default=None),
    session: Session = Depends(get_session),
):
    """Excel file: wages per worker, plus every entry with its rate and wage."""
    check_period(start, end)
    data = svc.wages_workbook(session, start, end, lang, worker_id)
    return _download(data, f"wages_{start.isoformat()}_{end.isoformat()}.xlsx")


@router.get("/production.xlsx")
def production_xlsx(
    start: date,
    end: date,
    group_by: GroupBy = "month",
    lang: Language = "en",
    worker_id: list[str] | None = Query(default=None),
    session: Session = Depends(get_session),
):
    """Excel file: production and wages per day, month or year."""
    check_period(start, end)
    data = svc.production_workbook(session, start, end, group_by, lang, worker_id)
    return _download(data, f"production_{group_by}_{start.isoformat()}_{end.isoformat()}.xlsx")
