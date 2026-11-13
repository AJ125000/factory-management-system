from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import ProductionCreate, ProductionOut, ProductionPage, ProductionUpdate
from ..services import production as svc
from ..services.rates import RateBook

router = APIRouter(prefix="/production", tags=["production"])


@router.get("", response_model=ProductionPage)
def list_entries(
    start: date | None = None,
    end: date | None = None,
    worker_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    total, entries = svc.list_entries(session, start, end, worker_id, limit, offset)
    book = RateBook.load(session)
    return ProductionPage(total=total, items=[svc.to_out(e, book) for e in entries])


@router.post("", response_model=ProductionOut, status_code=status.HTTP_201_CREATED)
def create_entry(data: ProductionCreate, session: Session = Depends(get_session)):
    entry = svc.create_entry(session, data)
    session.commit()
    return svc.to_out(entry, RateBook.load(session))


@router.get("/{entry_id}", response_model=ProductionOut)
def get_entry(entry_id: str, session: Session = Depends(get_session)):
    return svc.to_out(svc.get_entry(session, entry_id), RateBook.load(session))


@router.patch("/{entry_id}", response_model=ProductionOut)
def update_entry(entry_id: str, data: ProductionUpdate, session: Session = Depends(get_session)):
    entry = svc.update_entry(session, entry_id, data)
    session.commit()
    return svc.to_out(entry, RateBook.load(session))


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: str, session: Session = Depends(get_session)):
    svc.delete_entry(session, entry_id)
    session.commit()
