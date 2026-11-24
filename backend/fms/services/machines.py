"""Machines, the size tables of each machine type, and which loader works at each machine.

There can be several machines of each type (e.g. three table polish machines). Every
machine of a type is paid the same rates and uses the same size table; each machine
has its own loader. The owner adds machines and retires them; a machine is deleted
only if nothing was ever entered on it.

A loader assignment applies from its `effective_from` date until the next assignment
for the same machine, like rates. Replacing or swapping a loader is a new assignment
from a new date, so wages already earned are never moved to someone else.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..errors import Conflict, Invalid, NotFound
from ..models import LoaderAssignment, Machine, MachineSize, ProductionEntry, Worker
from ..schemas import (
    LoaderAssignmentCreate,
    LoaderAssignmentUpdate,
    MachineCreate,
    MachineSizeCreate,
    MachineSizeUpdate,
    MachineUpdate,
)
from ..wages import MachineKind, Role, has_loader, uses_size_table
from . import audit
from ._common import apply_changes, existing_replay

# Fixed ids of the machines added by migration 0003 (the same on every device).
BLOCK_CUTTING_ID = "00000000-0000-4000-8000-000000000101"
DOUBLE_EDGE_ID = "00000000-0000-4000-8000-000000000102"
TABLE_POLISH_ID = "00000000-0000-4000-8000-000000000103"
SINGLE_CUTTING_ID = "00000000-0000-4000-8000-000000000104"
BLOCK_CUTTER_ID = "00000000-0000-4000-8000-000000000105"  # added by migration 0005

MACHINE = "machine"
SIZE = "machine_size"
ASSIGNMENT = "loader_assignment"


# --------------------------------------------------------------------- machines
def list_machines(session: Session, include_inactive: bool = True) -> list[Machine]:
    stmt = select(Machine).order_by(Machine.sort_order, Machine.name_en)
    if not include_inactive:
        stmt = stmt.where(Machine.is_active.is_(True))
    return list(session.scalars(stmt))


def get_machine(session: Session, machine_id: str) -> Machine:
    machine = session.get(Machine, machine_id)
    if machine is None:
        raise NotFound("Machine not found", machine_id=machine_id)
    return machine


def known_machine(session: Session, machine_id: str) -> Machine:
    """The machine named in a request (a bad id is the request's fault: 422, not 404)."""
    machine = session.get(Machine, machine_id)
    if machine is None:
        raise Invalid("Unknown machine", reason="unknown_machine", machine_id=machine_id)
    return machine


def _unique_code(session: Session, kind: str) -> str:
    n = 2  # the first machine of each type (from the migration) is just "<kind>"
    while session.scalar(select(Machine.id).where(Machine.code == f"{kind}_{n}")):
        n += 1
    return f"{kind}_{n}"


def create_machine(session: Session, data: MachineCreate) -> Machine:
    kind = MachineKind(data.kind)
    # New machines go after the others of their type, so each type stays together.
    order = (
        session.scalar(select(func.max(Machine.sort_order)).where(Machine.kind == kind.value))
        or session.scalar(select(func.max(Machine.sort_order)))
        or 0
    )
    machine = Machine(
        code=_unique_code(session, kind.value),
        kind=kind.value,
        name_en=data.name_en,
        name_hi=data.name_hi or None,
        sort_order=order,
    )
    session.add(machine)
    session.flush()
    audit.record(
        session,
        "create",
        MACHINE,
        machine.id,
        f"Added machine {machine.name_en}",
        after=audit.snapshot(machine),
    )
    return machine


def count_entries(session: Session, machine_id: str) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(ProductionEntry)
            .where(ProductionEntry.machine_id == machine_id)
        )
        or 0
    )


def delete_machine(session: Session, machine_id: str) -> None:
    """Delete a machine nothing was entered on (e.g. added by mistake).

    A machine with production entries is retired instead (is_active false), so the
    wages earned on it stay in every report.
    """
    machine = get_machine(session, machine_id)
    entries = count_entries(session, machine.id)
    if entries:
        raise Conflict(
            "This machine has production entries. Stop using it instead, so its "
            "wages stay in the reports.",
            reason="machine_has_entries",
            production_entries=entries,
        )
    assignments = list(
        session.scalars(select(LoaderAssignment).where(LoaderAssignment.machine_id == machine.id))
    )
    audit.record(
        session,
        "delete",
        MACHINE,
        machine.id,
        f"Deleted machine {machine.name_en}",
        before={
            "machine": audit.snapshot(machine),
            "loader_assignments": [audit.snapshot(a) for a in assignments],
        },
    )
    for a in assignments:
        audit.tombstone(session, ASSIGNMENT, a.id)
        session.delete(a)
    audit.tombstone(session, MACHINE, machine.id)
    session.delete(machine)
    session.flush()


def update_machine(session: Session, machine_id: str, data: MachineUpdate) -> Machine:
    machine = get_machine(session, machine_id)
    before = audit.snapshot(machine)
    apply_changes(
        machine,
        data.model_dump(exclude_unset=True),
        required=("name_en", "is_active"),
        blank_to_none=("name_hi",),
    )
    session.flush()
    audit.record(
        session,
        "update",
        MACHINE,
        machine.id,
        f"Edited machine {machine.name_en}",
        before=before,
        after=audit.snapshot(machine),
    )
    return machine


# ------------------------------------------------------------------ size tables
def _fraction(value: Decimal) -> str:
    """2 -> "2", 1.5 -> "1½", 22.5 -> "22½", 2.25 -> "2.25"."""
    whole, rest = divmod(value, 1)
    if rest == 0:
        return str(int(whole))
    if rest == Decimal("0.5"):
        return f"{int(whole) if whole else ''}½"
    return format(value.normalize(), "f")


def size_label(length: Decimal, width: Decimal) -> str:
    return f"{_fraction(length)} × {_fraction(width)}"


def list_sizes(session: Session, kind: str | None = None) -> list[MachineSize]:
    stmt = select(MachineSize).order_by(MachineSize.kind, MachineSize.created_at)
    if kind:
        stmt = stmt.where(MachineSize.kind == kind)
    # Biggest first within a machine reads naturally on the owner's sheet.
    sizes = list(session.scalars(stmt).unique())
    sizes.sort(key=lambda s: (s.kind, -(s.length * s.width), -s.length))
    return sizes


def get_size(session: Session, size_id: str) -> MachineSize:
    size = session.get(MachineSize, size_id)
    if size is None:
        raise NotFound("Size not found", size_id=size_id)
    return size


def find_size(session: Session, kind: str, length: Decimal, width: Decimal) -> MachineSize | None:
    """The table size matching these measurements, either way round."""
    wanted = sorted((length, width))
    for size in list_sizes(session, kind):
        if sorted((size.length, size.width)) == wanted:
            return size
    return None


def _flush_size(session: Session) -> None:
    try:
        with session.begin_nested():
            session.flush()
    except IntegrityError as exc:
        raise Conflict(
            "This size is already in the table. Edit that size instead.",
            reason="duplicate_size",
        ) from exc


def create_size(session: Session, data: MachineSizeCreate) -> MachineSize:
    if replay := existing_replay(session, MachineSize, data.id, SIZE):
        return replay
    kind = MachineKind(data.kind)
    if not uses_size_table(kind):
        raise Invalid("This machine type has no size table", reason="no_size_table", kind=kind)
    if find_size(session, kind.value, data.length, data.width):
        raise Conflict(
            "This size is already in the table. Edit that size instead.",
            reason="duplicate_size",
        )
    size = MachineSize(
        **({"id": str(data.id)} if data.id else {}),
        kind=kind.value,
        length=data.length,
        width=data.width,
        rft=data.rft,
        sqft=data.sqft,
    )
    session.add(size)
    _flush_size(session)
    audit.record(
        session,
        "create",
        SIZE,
        size.id,
        f"Added size {size_label(size.length, size.width)} to {kind}: "
        f"{size.rft} running ft, {size.sqft} sq ft",
        after=audit.snapshot(size),
    )
    return size


def update_size(session: Session, size_id: str, data: MachineSizeUpdate) -> MachineSize:
    """Change a size. Entries already saved keep the figures they were saved with."""
    size = get_size(session, size_id)
    before = audit.snapshot(size)
    apply_changes(
        size, data.model_dump(exclude_unset=True), required=("length", "width", "rft", "sqft")
    )
    other = find_size(session, size.kind, size.length, size.width)
    if other is not None and other.id != size.id:
        raise Conflict(
            "This size is already in the table. Edit that size instead.",
            reason="duplicate_size",
        )
    _flush_size(session)
    audit.record(
        session,
        "update",
        SIZE,
        size.id,
        f"Edited size {size_label(size.length, size.width)}",
        before=before,
        after=audit.snapshot(size),
    )
    return size


def delete_size(session: Session, size_id: str) -> None:
    size = get_size(session, size_id)
    audit.record(
        session,
        "delete",
        SIZE,
        size.id,
        f"Removed size {size_label(size.length, size.width)}",
        before=audit.snapshot(size),
    )
    audit.tombstone(session, SIZE, size.id)
    session.delete(size)
    session.flush()


# ------------------------------------------------------------ loader assignments
class LoaderBook:
    """In-memory index of loader assignments for fast "loader on date X" lookups."""

    def __init__(self, assignments: Iterable[LoaderAssignment]) -> None:
        grouped: dict[str, list[tuple[date, str | None]]] = defaultdict(list)
        for a in assignments:
            grouped[a.machine_id].append((a.effective_from, a.worker_id))
        self._dates: dict[str, list[date]] = {}
        self._workers: dict[str, list[str | None]] = {}
        for machine_id, items in grouped.items():
            items.sort(key=lambda item: item[0])
            self._dates[machine_id] = [d for d, _ in items]
            self._workers[machine_id] = [w for _, w in items]

    @classmethod
    def load(cls, session: Session) -> LoaderBook:
        return cls(session.scalars(select(LoaderAssignment)))

    def loader_on(self, machine_id: str, on: date) -> str | None:
        dates = self._dates.get(machine_id)
        if not dates:
            return None
        i = bisect_right(dates, on) - 1
        return self._workers[machine_id][i] if i >= 0 else None


def list_assignments(session: Session, machine_id: str | None = None) -> list[LoaderAssignment]:
    stmt = select(LoaderAssignment).order_by(
        LoaderAssignment.machine_id, LoaderAssignment.effective_from.desc()
    )
    if machine_id:
        stmt = stmt.where(LoaderAssignment.machine_id == machine_id)
    return list(session.scalars(stmt))


def get_assignment(session: Session, assignment_id: str) -> LoaderAssignment:
    assignment = session.get(LoaderAssignment, assignment_id)
    if assignment is None:
        raise NotFound("Loader assignment not found", assignment_id=assignment_id)
    return assignment


def usable_loader(session: Session, worker_id: str) -> Worker:
    """A worker who can be paid as a loader."""
    worker = session.get(Worker, worker_id)
    if worker is None:
        raise Invalid("Unknown worker", reason="unknown_worker", worker_id=worker_id)
    if worker.worker_type.role != Role.LOADER:
        raise Invalid(
            f"{worker.name_en} is not a loader", reason="not_a_loader", worker_id=worker_id
        )
    return worker


def _flush_assignment(session: Session) -> None:
    try:
        with session.begin_nested():
            session.flush()
    except IntegrityError as exc:
        raise Conflict(
            "This machine already has a loader change on that date. Edit that one instead.",
            reason="duplicate_effective_date",
        ) from exc


def _describe(session: Session, a: LoaderAssignment) -> str:
    machine = session.get(Machine, a.machine_id)
    worker = session.get(Worker, a.worker_id) if a.worker_id else None
    who = worker.name_en if worker else "no loader"
    return f"{machine.name_en if machine else '?'}: {who} from {a.effective_from.isoformat()}"


def create_assignment(session: Session, data: LoaderAssignmentCreate) -> LoaderAssignment:
    if replay := existing_replay(session, LoaderAssignment, data.id, ASSIGNMENT):
        return replay
    machine = known_machine(session, data.machine_id)
    if not has_loader(machine.kind):
        raise Invalid(
            "This machine is paid per shift and has no loader",
            reason="machine_has_no_loader",
            machine_id=machine.id,
        )
    if data.worker_id:
        usable_loader(session, data.worker_id)
    assignment = LoaderAssignment(
        **({"id": str(data.id)} if data.id else {}),
        machine_id=machine.id,
        worker_id=data.worker_id or None,
        effective_from=data.effective_from,
        note=data.note or None,
    )
    session.add(assignment)
    _flush_assignment(session)
    audit.record(
        session,
        "create",
        ASSIGNMENT,
        assignment.id,
        f"Loader at {_describe(session, assignment)}",
        after=audit.snapshot(assignment),
    )
    return assignment


def update_assignment(
    session: Session, assignment_id: str, data: LoaderAssignmentUpdate
) -> LoaderAssignment:
    """Correct an assignment. This deliberately moves loader pay for the period it covers."""
    assignment = get_assignment(session, assignment_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("worker_id"):
        usable_loader(session, changes["worker_id"])
    before = audit.snapshot(assignment)
    apply_changes(
        assignment, changes, required=("effective_from",), blank_to_none=("note", "worker_id")
    )
    _flush_assignment(session)
    audit.record(
        session,
        "update",
        ASSIGNMENT,
        assignment.id,
        f"Corrected loader at {_describe(session, assignment)}",
        before=before,
        after=audit.snapshot(assignment),
    )
    return assignment


def delete_assignment(session: Session, assignment_id: str) -> None:
    assignment = get_assignment(session, assignment_id)
    audit.record(
        session,
        "delete",
        ASSIGNMENT,
        assignment.id,
        f"Removed loader change {_describe(session, assignment)}",
        before=audit.snapshot(assignment),
    )
    audit.tombstone(session, ASSIGNMENT, assignment.id)
    session.delete(assignment)
    session.flush()
