from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import CurrentRateOut, RateCreate, RateOut, RateUpdate
from ..services import rates as svc
from ..services.worker_types import list_worker_types
from ..util import today
from ..wages import SCHEME_COMPONENTS, PayScheme

router = APIRouter(prefix="/rates", tags=["rates"])


@router.get("", response_model=list[RateOut])
def list_rates(worker_type_id: str | None = None, session: Session = Depends(get_session)):
    """Full rate history, newest first within each worker type and component."""
    return svc.list_rates(session, worker_type_id)


@router.get("/current", response_model=list[CurrentRateOut])
def current_rates(on: date | None = None, session: Session = Depends(get_session)):
    """The rate in effect on a date (default today) for every active worker type."""
    on = on or today()
    book = svc.RateBook.load(session)
    out = []
    for wt in list_worker_types(session):
        for component in SCHEME_COMPONENTS[PayScheme(wt.pay_scheme)]:
            found = book.lookup_with_date(wt.id, component, on)
            out.append(
                CurrentRateOut(
                    worker_type_id=wt.id,
                    component=component,
                    rate_per_sqft=found[0] if found else None,
                    effective_from=found[1] if found else None,
                )
            )
    return out


@router.post("", response_model=RateOut, status_code=status.HTTP_201_CREATED)
def create_rate(data: RateCreate, session: Session = Depends(get_session)):
    rate = svc.create_rate(session, data)
    session.commit()
    return rate


@router.patch("/{rate_id}", response_model=RateOut)
def update_rate(rate_id: str, data: RateUpdate, session: Session = Depends(get_session)):
    rate = svc.update_rate(session, rate_id, data)
    session.commit()
    return rate


@router.delete("/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rate(rate_id: str, session: Session = Depends(get_session)):
    svc.delete_rate(session, rate_id)
    session.commit()
