from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import DeleteImpact, WorkerCreate, WorkerOut, WorkerUpdate
from ..services import workers as svc

router = APIRouter(prefix="/workers", tags=["workers"])


@router.get("", response_model=list[WorkerOut])
def list_workers(
    include_archived: bool = False,
    search: str | None = Query(default=None, max_length=120),
    session: Session = Depends(get_session),
):
    return svc.list_workers(session, include_archived, search)


@router.post("", response_model=WorkerOut, status_code=status.HTTP_201_CREATED)
def create_worker(data: WorkerCreate, session: Session = Depends(get_session)):
    worker = svc.create_worker(session, data)
    session.commit()
    return worker


@router.get("/{worker_id}", response_model=WorkerOut)
def get_worker(worker_id: str, session: Session = Depends(get_session)):
    return svc.get_worker(session, worker_id)


@router.patch("/{worker_id}", response_model=WorkerOut)
def update_worker(worker_id: str, data: WorkerUpdate, session: Session = Depends(get_session)):
    worker = svc.update_worker(session, worker_id, data)
    session.commit()
    return worker


@router.post("/{worker_id}/archive", response_model=WorkerOut)
def archive_worker(worker_id: str, session: Session = Depends(get_session)):
    worker = svc.archive_worker(session, worker_id)
    session.commit()
    return worker


@router.post("/{worker_id}/restore", response_model=WorkerOut)
def restore_worker(worker_id: str, session: Session = Depends(get_session)):
    worker = svc.restore_worker(session, worker_id)
    session.commit()
    return worker


@router.get("/{worker_id}/delete-impact", response_model=DeleteImpact)
def delete_impact(worker_id: str, session: Session = Depends(get_session)):
    """What deleting this worker would remove. Show it to the owner before deleting."""
    svc.get_worker(session, worker_id)
    return DeleteImpact(
        worker_id=worker_id, production_entries=svc.count_entries(session, worker_id)
    )


@router.delete("/{worker_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_worker(
    worker_id: str,
    confirm_entries: int = Query(ge=0, description="Entry count from /delete-impact"),
    session: Session = Depends(get_session),
):
    svc.delete_worker(session, worker_id, confirm_entries)
    session.commit()
