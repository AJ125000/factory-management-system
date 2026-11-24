from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..errors import Conflict, Invalid, NotFound
from ..models import Machine, MachineSize, ProductionEntry, Worker
from ..schemas import (
    ProductionCreate,
    ProductionOut,
    ProductionUpdate,
    WageLineOut,
    WagePreviewIn,
    WagePreviewOut,
)
from ..util import today
from ..wages import (
    LOADER_UNLOADING,
    OPERATOR_CUTTING,
    InvalidPieceError,
    MachineKind,
    MissingRateError,
    Piece,
    Role,
    WageResult,
    bases,
    calculate_wage,
    is_shift_paid,
    perimeter,
)
from . import audit
from ._common import apply_changes, existing_replay
from .machines import (
    BLOCK_CUTTING_ID,
    LoaderBook,
    find_size,
    known_machine,
    size_label,
    usable_loader,
)
from .rates import RateBook

ENTITY = "production_entry"


# ------------------------------------------------------------------ pieces
def resolve_piece(
    session: Session,
    machine: Machine,
    *,
    length_ft: Decimal | None,
    width_ft: Decimal | None,
    size_id: str | None,
    cuts: int,
    batti: int | None,
    shift: str | None = None,
) -> dict[str, Any]:
    """What one piece counts for on this machine; the columns to store on the entry.

    Sizes in a machine's size table count for the table's figures (the owner's "market
    standard"), other sizes for their true area and perimeter.
    """
    kind = MachineKind(machine.kind)

    def need_dimensions() -> tuple[Decimal, Decimal]:
        if length_ft is None or width_ft is None:
            raise Invalid("Enter the length and width", reason="size_required")
        return length_ft, width_ft

    def table_size(sid: str) -> MachineSize:
        size = session.get(MachineSize, sid)
        if size is None or size.kind != machine.kind:
            raise Invalid("Unknown size for this machine", reason="unknown_size", size_id=sid)
        return size

    out: dict[str, Any] = {
        "length_ft": None,
        "width_ft": None,
        "size_id": None,
        "size_label": None,
        "piece_rft": None,
        "cuts": 0,
        "batti": None,
        "shift": None,
    }
    if kind is MachineKind.BLOCK_CUTTER:
        if shift is None:
            raise Invalid("Pick the shift (day or night)", reason="shift_required")
        out |= {"piece_sqft": Decimal(0), "shift": shift, "quantity": 1}
    elif kind is MachineKind.SINGLE_CUTTING:
        if not size_id:
            raise Invalid(
                "Pick a size. A new size must first be added to the machine's size table.",
                reason="size_required",
            )
        size = table_size(size_id)
        out |= {
            "size_id": size.id,
            "size_label": size_label(size.length, size.width),
            "piece_sqft": size.sqft,
            "piece_rft": size.rft,
        }
    elif kind is MachineKind.DOUBLE_EDGE:
        size = table_size(size_id) if size_id else None
        if size is None:
            length, width = need_dimensions()
            size = find_size(session, machine.kind, length, width)
        if size is not None:
            out |= {
                "length_ft": size.length,
                "width_ft": size.width,
                "size_id": size.id,
                "piece_sqft": size.sqft,
                "piece_rft": size.rft,
            }
        else:
            out |= {
                "length_ft": length,
                "width_ft": width,
                "piece_sqft": length * width,
                "piece_rft": perimeter(length, width),
            }
        out["size_label"] = size_label(out["length_ft"], out["width_ft"])
    else:
        length, width = need_dimensions()
        out |= {"length_ft": length, "width_ft": width, "piece_sqft": length * width}
        if kind is MachineKind.BLOCK_CUTTING:
            out["cuts"] = cuts
        else:  # table polish
            if batti is None:
                raise Invalid("Pick the number of batti", reason="batti_required")
            out["batti"] = batti
    return out


def piece_of(entry: ProductionEntry) -> Piece:
    return Piece(entry.piece_sqft, entry.piece_rft, entry.cuts, entry.quantity, entry.batti)


_piece = piece_of


def splitting_sqft(kind: str, piece: Piece) -> tuple[Decimal | None, Decimal | None]:
    """Splitting machine: the sq ft the operator's cutting and the loader's unloading
    are paid on. (None, None) for other machines."""
    if MachineKind(kind) is not MachineKind.BLOCK_CUTTING:
        return None, None
    return (
        bases(kind, Role.OPERATOR, piece)[OPERATOR_CUTTING],
        bases(kind, Role.LOADER, piece)[LOADER_UNLOADING],
    )


# ------------------------------------------------------------------ wages
@dataclass(frozen=True)
class Pay:
    """What one worker earns from one entry."""

    worker_id: str | None  # None: the machine had no loader on that date
    role: Role
    result: WageResult | None  # None: a rate is missing
    missing: list[str]

    @property
    def total(self) -> Decimal | None:
        return self.result.total if self.result else None


def _calc(
    book: RateBook, machine: Machine, role: Role, piece: Piece, on: date
) -> tuple[WageResult | None, list[str]]:
    try:
        rates = book.rates_for(machine.kind, role, piece, on)
        return calculate_wage(machine.kind, role, piece, rates), []
    except MissingRateError as exc:
        return None, exc.components
    except InvalidPieceError:
        return None, ["batti"]


def entry_pays(entry: ProductionEntry, book: RateBook, loaders: LoaderBook) -> list[Pay]:
    """The operator's pay and the loader's pay from one entry.

    Entries made for a loader before loader pay became automatic pay just that loader.
    """
    piece = _piece(entry)
    if is_shift_paid(entry.machine.kind):
        # Whoever worked the shift is paid for it; there is no loader.
        result, missing = _calc(book, entry.machine, Role.OPERATOR, piece, entry.entry_date)
        return [Pay(entry.worker_id, Role.OPERATOR, result, missing)]
    role = Role(entry.worker_type.role)
    result, missing = _calc(book, entry.machine, role, piece, entry.entry_date)
    pays = [Pay(entry.worker_id, role, result, missing)]
    if role is Role.OPERATOR:
        loader = entry.loader_id or loaders.loader_on(entry.machine_id, entry.entry_date)
        result, missing = _calc(book, entry.machine, Role.LOADER, piece, entry.entry_date)
        pays.append(Pay(loader, Role.LOADER, result, missing))
    return pays


def _lines_out(result: WageResult | None) -> list[WageLineOut]:
    if result is None:
        return []
    return [
        WageLineOut(
            component=line.component,
            basis=line.basis,
            unit=line.unit,
            rate=line.rate,
            amount=line.amount,
        )
        for line in result.lines
    ]


def to_out(
    entry: ProductionEntry,
    book: RateBook,
    loaders: LoaderBook,
    paid_as: Role = Role.OPERATOR,
) -> ProductionOut:
    """The entry with its wages. `wage` is the pay of the worker in role `paid_as`."""
    pays = entry_pays(entry, book, loaders)
    out = ProductionOut.model_validate(entry)
    out.cutting_sqft, out.unloading_sqft = splitting_sqft(entry.machine.kind, piece_of(entry))
    main = next((p for p in pays if p.role is paid_as), pays[0])
    out.paid_as = main.role
    out.paid_worker_id = main.worker_id
    out.wage = main.total
    out.wage_lines = _lines_out(main.result)
    out.missing_rates = main.missing
    loader = next((p for p in pays if p.role is Role.LOADER), None)
    if loader is not None and len(pays) > 1:
        out.loader_worker_id = loader.worker_id
        out.loader_wage = loader.total
        out.loader_wage_lines = _lines_out(loader.result)
        out.loader_missing_rates = loader.missing
        out.no_loader = loader.worker_id is None
    return out


def _operator(session: Session, worker_id: str, machine: Machine) -> Worker:
    """The worker an entry is made for: an operator, or anyone on a per-shift machine."""
    worker = session.get(Worker, worker_id)
    if worker is None:
        raise Invalid("Unknown worker", reason="unknown_worker", worker_id=worker_id)
    if worker.worker_type.role == Role.LOADER and not is_shift_paid(machine.kind):
        raise Invalid(
            "Loaders are paid automatically from the machine operators' entries. "
            "Enter the operator's work instead.",
            reason="loader_paid_automatically",
        )
    return worker


def _active_machine(session: Session, machine_id: str | None) -> Machine:
    machine = known_machine(session, machine_id or BLOCK_CUTTING_ID)
    if not machine.is_active:
        raise Invalid(
            "This machine is no longer in use", reason="machine_inactive", machine_id=machine.id
        )
    return machine


def preview_wage(session: Session, data: WagePreviewIn) -> WagePreviewOut:
    """What an entry would pay, without saving it (live preview while typing)."""
    machine = _active_machine(session, data.machine_id)
    _operator(session, data.worker_id, machine)
    if data.loader_id and not is_shift_paid(machine.kind):
        usable_loader(session, data.loader_id)
    fields = resolve_piece(
        session,
        machine,
        length_ft=data.length_ft,
        width_ft=data.width_ft,
        size_id=data.size_id,
        cuts=data.cuts,
        batti=data.batti,
        shift=data.shift,
    )
    quantity = fields.pop("quantity", data.quantity)
    piece = Piece(
        fields["piece_sqft"], fields["piece_rft"], fields["cuts"], quantity, fields["batti"]
    )
    book = RateBook.load(session)
    result, missing = _calc(book, machine, Role.OPERATOR, piece, data.entry_date)
    cutting_sqft, unloading_sqft = splitting_sqft(machine.kind, piece)
    if is_shift_paid(machine.kind):
        return WagePreviewOut(
            area_sqft=piece.total_sqft,
            rft_total=None,
            piece_sqft=piece.sqft,
            piece_rft=None,
            wage=result.total if result else None,
            wage_lines=_lines_out(result),
            missing_rates=missing,
            loader_worker_id=None,
            loader_wage=None,
            loader_wage_lines=[],
            loader_missing_rates=[],
            no_loader=False,
        )
    loader_result, loader_missing = _calc(book, machine, Role.LOADER, piece, data.entry_date)
    loader = data.loader_id or LoaderBook.load(session).loader_on(machine.id, data.entry_date)
    return WagePreviewOut(
        area_sqft=piece.total_sqft,
        rft_total=piece.total_rft,
        cutting_sqft=cutting_sqft,
        unloading_sqft=unloading_sqft,
        piece_sqft=piece.sqft,
        piece_rft=piece.rft,
        wage=result.total if result else None,
        wage_lines=_lines_out(result),
        missing_rates=missing,
        loader_worker_id=loader,
        loader_wage=loader_result.total if loader_result else None,
        loader_wage_lines=_lines_out(loader_result),
        loader_missing_rates=loader_missing,
        no_loader=loader is None,
    )


# ------------------------------------------------------------------ queries
def list_entries(
    session: Session,
    start: date | None = None,
    end: date | None = None,
    worker_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    machine_id: str | None = None,
) -> tuple[int, list[ProductionEntry]]:
    """Entries in a period. A worker filter also finds a loader's entries by their override;
    entries a loader is paid for through their machine assignment are in the wages report."""
    conditions = []
    if start:
        conditions.append(ProductionEntry.entry_date >= start)
    if end:
        conditions.append(ProductionEntry.entry_date <= end)
    if worker_id:
        conditions.append(
            or_(ProductionEntry.worker_id == worker_id, ProductionEntry.loader_id == worker_id)
        )
    if machine_id:
        conditions.append(ProductionEntry.machine_id == machine_id)
    total = session.scalar(select(func.count()).select_from(ProductionEntry).where(*conditions))
    stmt = (
        select(ProductionEntry)
        .where(*conditions)
        .order_by(ProductionEntry.entry_date.desc(), ProductionEntry.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return total or 0, list(session.scalars(stmt).unique())


def get_entry(session: Session, entry_id: str) -> ProductionEntry:
    entry = session.get(ProductionEntry, entry_id)
    if entry is None:
        raise NotFound("Production entry not found", entry_id=entry_id)
    return entry


# ------------------------------------------------------------------ changes
def _usable_worker(session: Session, worker_id: str, machine: Machine) -> Worker:
    worker = _operator(session, worker_id, machine)
    if worker.is_archived:
        raise Conflict(
            "This worker is archived. Restore them before adding production.",
            reason="worker_archived",
        )
    return worker


def _check_date(entry_date: date) -> None:
    if entry_date > today():
        raise Invalid(
            "The entry date can't be in the future",
            reason="future_date",
            entry_date=entry_date.isoformat(),
        )


def _check_shift_free(
    session: Session, worker_id: str, on: date, shift: str | None, entry_id: str | None = None
) -> None:
    """A worker can be paid for a shift once (day and night on one date is a double shift)."""
    if shift is None:
        return
    stmt = (
        select(ProductionEntry.id)
        .join(Machine, Machine.id == ProductionEntry.machine_id)
        .where(
            ProductionEntry.worker_id == worker_id,
            ProductionEntry.entry_date == on,
            ProductionEntry.shift == shift,
            Machine.kind == MachineKind.BLOCK_CUTTER.value,
        )
    )
    if entry_id:
        stmt = stmt.where(ProductionEntry.id != entry_id)
    if session.scalar(stmt.limit(1)):
        raise Conflict(
            "This worker already has this shift on that date",
            reason="duplicate_shift",
            shift=shift,
        )


def _summary(entry: ProductionEntry, verb: str) -> str:
    return (
        f"{verb} production for {entry.worker.name_en} on {entry.machine.name_en} "
        f"on {entry.entry_date.isoformat()}"
    )


def create_entry(session: Session, data: ProductionCreate) -> ProductionEntry:
    if replay := existing_replay(session, ProductionEntry, data.id, ENTITY):
        return replay
    machine = _active_machine(session, data.machine_id)
    worker = _usable_worker(session, data.worker_id, machine)
    _check_date(data.entry_date)
    loader_id = None if is_shift_paid(machine.kind) else data.loader_id
    if loader_id:
        usable_loader(session, loader_id)
    fields = resolve_piece(
        session,
        machine,
        length_ft=data.length_ft,
        width_ft=data.width_ft,
        size_id=data.size_id,
        cuts=data.cuts,
        batti=data.batti,
        shift=data.shift,
    )
    _check_shift_free(session, worker.id, data.entry_date, fields["shift"])
    quantity = fields.pop("quantity", data.quantity)
    entry = ProductionEntry(
        **({"id": str(data.id)} if data.id else {}),
        worker_id=worker.id,
        worker_type_id=worker.worker_type_id,
        machine_id=machine.id,
        entry_date=data.entry_date,
        quantity=quantity,
        loader_id=loader_id or None,
        notes=data.notes or None,
        **fields,
    )
    session.add(entry)
    session.flush()
    session.refresh(entry)
    audit.record(
        session, "create", ENTITY, entry.id, _summary(entry, "Added"), after=audit.snapshot(entry)
    )
    return entry


SIZE_FIELDS = ("machine_id", "length_ft", "width_ft", "size_id", "cuts", "batti", "shift")


def update_entry(session: Session, entry_id: str, data: ProductionUpdate) -> ProductionEntry:
    entry = get_entry(session, entry_id)
    changes = data.model_dump(exclude_unset=True)
    new_machine_id = changes.get("machine_id") or entry.machine_id
    target = (
        entry.machine
        if new_machine_id == entry.machine_id
        else known_machine(session, new_machine_id)
    )
    if changes.get("worker_id") and changes["worker_id"] != entry.worker_id:
        worker = _usable_worker(session, changes["worker_id"], target)
        entry.worker_type_id = worker.worker_type_id
    elif target is not entry.machine:
        _operator(session, entry.worker_id, target)  # e.g. a loader moved off a shift
    if is_shift_paid(target.kind):
        changes.pop("loader_id", None)
        changes.pop("quantity", None)
    if changes.get("entry_date"):
        _check_date(changes["entry_date"])
    if changes.get("loader_id"):
        usable_loader(session, changes["loader_id"])

    before = audit.snapshot(entry)
    size_changes = {k: v for k, v in changes.items() if k in SIZE_FIELDS and v is not None}
    if any(getattr(entry, k) != v for k, v in size_changes.items()):
        # Worked out again only when the size changes, so a later edit of the size
        # table doesn't silently change an entry whose pieces were just recounted.
        machine_id = size_changes.get("machine_id", entry.machine_id)
        machine = (
            _active_machine(session, machine_id)
            if machine_id != entry.machine_id
            else entry.machine
        )
        current = {k: getattr(entry, k) for k in SIZE_FIELDS}
        merged = current | size_changes
        if "size_id" not in size_changes and (
            machine_id != entry.machine_id  # a size belongs to the old machine
            or "length_ft" in size_changes
            or "width_ft" in size_changes  # new measurements: look the size up again
        ):
            merged["size_id"] = None
        fields = resolve_piece(
            session,
            machine,
            length_ft=merged["length_ft"],
            width_ft=merged["width_ft"],
            size_id=merged["size_id"],
            cuts=merged["cuts"],
            batti=merged["batti"],
            shift=merged["shift"],
        )
        if is_shift_paid(machine.kind):
            entry.loader_id = None
        entry.machine_id = machine.id
        for key, value in fields.items():
            setattr(entry, key, value)
    if entry.shift is not None:
        _check_shift_free(
            session,
            changes.get("worker_id") or entry.worker_id,
            changes.get("entry_date") or entry.entry_date,
            entry.shift,
            entry.id,
        )
    other = {k: v for k, v in changes.items() if k not in SIZE_FIELDS}
    apply_changes(
        entry,
        other,
        required=("worker_id", "entry_date", "quantity"),
        blank_to_none=("notes", "loader_id"),
    )
    session.flush()
    session.expire(entry, ["machine", "worker", "worker_type"])
    session.refresh(entry)
    audit.record(
        session,
        "update",
        ENTITY,
        entry.id,
        _summary(entry, "Edited"),
        before=before,
        after=audit.snapshot(entry),
    )
    return entry


def delete_entry(session: Session, entry_id: str) -> None:
    entry = get_entry(session, entry_id)
    audit.record(
        session,
        "delete",
        ENTITY,
        entry.id,
        _summary(entry, "Deleted"),
        before=audit.snapshot(entry),
    )
    audit.tombstone(session, ENTITY, entry.id)
    session.delete(entry)
    session.flush()
