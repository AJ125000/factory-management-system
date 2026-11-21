from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import (
    LoaderAssignmentCreate,
    LoaderAssignmentOut,
    LoaderAssignmentUpdate,
    MachineOut,
    MachineSizeCreate,
    MachineSizeOut,
    MachineSizeUpdate,
    MachineUpdate,
)
from ..services import machines as svc

router = APIRouter(tags=["machines"])


@router.get("/machines", response_model=list[MachineOut])
def list_machines(session: Session = Depends(get_session)):
    return svc.list_machines(session)


@router.patch("/machines/{machine_id}", response_model=MachineOut)
def update_machine(machine_id: str, data: MachineUpdate, session: Session = Depends(get_session)):
    machine = svc.update_machine(session, machine_id, data)
    session.commit()
    return machine


# ------------------------------------------------------------------ size tables
@router.get("/machine-sizes", response_model=list[MachineSizeOut])
def list_sizes(machine_id: str | None = None, session: Session = Depends(get_session)):
    return svc.list_sizes(session, machine_id)


@router.post("/machine-sizes", response_model=MachineSizeOut, status_code=status.HTTP_201_CREATED)
def create_size(data: MachineSizeCreate, session: Session = Depends(get_session)):
    size = svc.create_size(session, data)
    session.commit()
    return size


@router.patch("/machine-sizes/{size_id}", response_model=MachineSizeOut)
def update_size(size_id: str, data: MachineSizeUpdate, session: Session = Depends(get_session)):
    size = svc.update_size(session, size_id, data)
    session.commit()
    return size


@router.delete("/machine-sizes/{size_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_size(size_id: str, session: Session = Depends(get_session)):
    svc.delete_size(session, size_id)
    session.commit()


# ----------------------------------------------------------- loader assignments
@router.get("/loader-assignments", response_model=list[LoaderAssignmentOut])
def list_assignments(machine_id: str | None = None, session: Session = Depends(get_session)):
    """Every loader change, newest first within each machine."""
    return svc.list_assignments(session, machine_id)


@router.post(
    "/loader-assignments",
    response_model=LoaderAssignmentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(data: LoaderAssignmentCreate, session: Session = Depends(get_session)):
    assignment = svc.create_assignment(session, data)
    session.commit()
    return assignment


@router.patch("/loader-assignments/{assignment_id}", response_model=LoaderAssignmentOut)
def update_assignment(
    assignment_id: str, data: LoaderAssignmentUpdate, session: Session = Depends(get_session)
):
    assignment = svc.update_assignment(session, assignment_id, data)
    session.commit()
    return assignment


@router.delete("/loader-assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(assignment_id: str, session: Session = Depends(get_session)):
    svc.delete_assignment(session, assignment_id)
    session.commit()
