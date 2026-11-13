from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import WorkerTypeCreate, WorkerTypeOut, WorkerTypeUpdate
from ..services import worker_types as svc

router = APIRouter(prefix="/worker-types", tags=["worker types"])


@router.get("", response_model=list[WorkerTypeOut])
def list_worker_types(include_inactive: bool = False, session: Session = Depends(get_session)):
    return svc.list_worker_types(session, include_inactive)


@router.post("", response_model=WorkerTypeOut, status_code=status.HTTP_201_CREATED)
def create_worker_type(data: WorkerTypeCreate, session: Session = Depends(get_session)):
    wt = svc.create_worker_type(session, data)
    session.commit()
    return wt


@router.patch("/{worker_type_id}", response_model=WorkerTypeOut)
def update_worker_type(
    worker_type_id: str, data: WorkerTypeUpdate, session: Session = Depends(get_session)
):
    wt = svc.update_worker_type(session, worker_type_id, data)
    session.commit()
    return wt
