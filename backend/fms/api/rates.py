from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import CurrentRateOut, RateCreate, RateOut, RateUpdate
from ..services import rates as svc
from ..util import today
from ..wages import MachineKind, allowed_components, batti_of, component_unit

router = APIRouter(prefix="/rates", tags=["rates"])


@router.get("", response_model=list[RateOut])
def list_rates(kind: str | None = None, session: Session = Depends(get_session)):
    """Full rate history, newest first within each machine type and component."""
    return svc.list_rates(session, kind)


@router.get("/current", response_model=list[CurrentRateOut])
def current_rates(on: date | None = None, session: Session = Depends(get_session)):
    """The rate in effect on a date (default today) for every machine type.

    Table polish lists only the batti counts that have a rate.
    """
    on = on or today()
    book = svc.RateBook.load(session)
    out = []
    for kind in MachineKind:
        used = book.components(kind)
        for component in allowed_components(kind):
            if kind is MachineKind.TABLE_POLISH and batti_of(component) and component not in used:
                continue
            found = book.lookup_with_date(kind, component, on)
            out.append(
                CurrentRateOut(
                    kind=kind,
                    component=component,
                    unit=component_unit(kind, component),
                    rate=found[0] if found else None,
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
