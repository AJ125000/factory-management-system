"""Wage formulas - pure functions with no database access.

Money uses Decimal (never float). Each wage line is rounded to the paisa (half-up),
and an entry's total is the sum of its rounded lines.

Every production entry is made for a machine OPERATOR on one machine. The loader
assigned to that machine is paid from the same entry automatically. What each is paid
depends on the kind of machine (from the owner's rate sheet, Nov 2026):

* Block cutting (the original machine; the 2 x confirmed by the owner):
      operator  cutting   = 2 x piece_sqft x cuts x pieces x rate/sq ft
      loader    loading   = piece_sqft x pieces x rate/sq ft
                unloading = piece_sqft x (1 + cuts) x pieces x rate/sq ft
* Double edge cutting and single cutting:
      operator  cutting   = piece_rft x pieces x rate/running ft
      loader    unloading = piece_sqft x pieces x rate/sq ft
* Table polish (the rate depends on the number of batti):
      operator  polish_N  = piece_sqft x pieces x rate/sq ft for N batti
      loader    unloading = piece_sqft x pieces x rate/sq ft
* Block cutter (attendance, added Nov 2026): a fixed amount per shift worked, day or
  night. One entry is one shift of one worker; there is no loader.
      worker    shift     = 1 x rate/shift

piece_sqft and piece_rft come from the machine's size table where it has one (the
"market standard" figures), otherwise from the true area and perimeter.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


class Role(StrEnum):
    OPERATOR = "operator"
    LOADER = "loader"


class MachineKind(StrEnum):
    BLOCK_CUTTING = "block_cutting"
    DOUBLE_EDGE = "double_edge"
    TABLE_POLISH = "table_polish"
    SINGLE_CUTTING = "single_cutting"
    BLOCK_CUTTER = "block_cutter"  # paid per shift (not the splitting machine, block_cutting)


class Shift(StrEnum):
    DAY = "day"
    NIGHT = "night"


class Unit(StrEnum):
    SQFT = "sqft"
    RFT = "rft"
    SHIFT = "shift"


# Rate components. Table polish has one per batti count: "polish_1", "polish_4", ...
CUTTING = "cutting"
LOADING = "loading"
UNLOADING = "unloading"
SHIFT_PAY = "shift"
OPERATOR_CUTTING = CUTTING  # the splitting machine's "machine man production"
LOADER_UNLOADING = UNLOADING
MAX_BATTI = 9
_POLISH = re.compile(r"^polish_([1-9])$")


def polish_component(batti: int) -> str:
    return f"polish_{batti}"


def batti_of(component: str) -> int | None:
    match = _POLISH.match(component)
    return int(match.group(1)) if match else None


def allowed_components(kind: MachineKind | str) -> tuple[str, ...]:
    """Every rate a machine of this kind can have."""
    kind = MachineKind(kind)
    if kind is MachineKind.BLOCK_CUTTING:
        return (CUTTING, LOADING, UNLOADING)
    if kind is MachineKind.TABLE_POLISH:
        return (*(polish_component(n) for n in range(1, MAX_BATTI + 1)), UNLOADING)
    if kind is MachineKind.BLOCK_CUTTER:
        return (SHIFT_PAY,)
    return (CUTTING, UNLOADING)


def is_allowed_component(kind: MachineKind | str, component: str) -> bool:
    return component in allowed_components(kind)


def component_unit(kind: MachineKind | str, component: str) -> Unit:
    """Whether a rate is per square foot, per running foot or per shift."""
    if component == SHIFT_PAY:
        return Unit.SHIFT
    if component == CUTTING and MachineKind(kind) in (
        MachineKind.DOUBLE_EDGE,
        MachineKind.SINGLE_CUTTING,
    ):
        return Unit.RFT
    return Unit.SQFT


def uses_size_table(kind: MachineKind | str) -> bool:
    return MachineKind(kind) in (MachineKind.DOUBLE_EDGE, MachineKind.SINGLE_CUTTING)


PAISA = Decimal("0.01")
ZERO = Decimal("0.00")


def to_paise(amount: Decimal) -> Decimal:
    return amount.quantize(PAISA, rounding=ROUND_HALF_UP)


def is_shift_paid(kind: MachineKind | str) -> bool:
    """Paid a fixed amount per shift (attendance), with no sizes and no loader."""
    return MachineKind(kind) is MachineKind.BLOCK_CUTTER


def has_loader(kind: MachineKind | str) -> bool:
    return not is_shift_paid(kind)


def perimeter(length: Decimal, width: Decimal) -> Decimal:
    return 2 * (length + width)


@dataclass(frozen=True)
class Piece:
    """One production entry: `quantity` identical pieces."""

    sqft: Decimal  # area of one piece
    rft: Decimal | None  # running feet of one piece (cutting machines with Rft rates)
    cuts: int
    quantity: int
    batti: int | None = None

    @property
    def total_sqft(self) -> Decimal:
        return self.sqft * self.quantity

    @property
    def total_rft(self) -> Decimal | None:
        return None if self.rft is None else self.rft * self.quantity


@dataclass(frozen=True)
class WageLine:
    component: str
    basis: Decimal  # the sq ft or running ft the rate is multiplied by
    unit: Unit
    rate: Decimal
    amount: Decimal


@dataclass(frozen=True)
class WageResult:
    lines: tuple[WageLine, ...]

    @property
    def total(self) -> Decimal:
        return sum((line.amount for line in self.lines), ZERO)


class MissingRateError(Exception):
    def __init__(self, components: list[str]) -> None:
        super().__init__(f"No rate set for: {', '.join(components)}")
        self.components = components


class InvalidPieceError(ValueError):
    pass


def bases(kind: MachineKind | str, role: Role | str, piece: Piece) -> dict[str, Decimal]:
    """The sq ft / running ft each rate component is multiplied by."""
    kind, role = MachineKind(kind), Role(role)
    qty = piece.quantity
    if kind is MachineKind.BLOCK_CUTTER:
        # Whoever is on the entry is paid for the shift, whatever their usual work.
        return {SHIFT_PAY: Decimal(qty)}
    if kind is MachineKind.BLOCK_CUTTING:
        if role is Role.OPERATOR:
            return {CUTTING: 2 * piece.sqft * piece.cuts * qty}
        return {LOADING: piece.sqft * qty, UNLOADING: piece.sqft * (1 + piece.cuts) * qty}
    if role is Role.LOADER:
        return {UNLOADING: piece.sqft * qty}
    if kind is MachineKind.TABLE_POLISH:
        if piece.batti is None:
            raise InvalidPieceError("Table polish needs the number of batti")
        return {polish_component(piece.batti): piece.sqft * qty}
    if piece.rft is None:
        raise InvalidPieceError("Cutting by running feet needs the running feet per piece")
    return {CUTTING: piece.rft * qty}


def calculate_wage(
    kind: MachineKind | str,
    role: Role | str,
    piece: Piece,
    rates: Mapping[str, Decimal | None],
) -> WageResult:
    """Wage for one entry. Raises MissingRateError if a needed rate is absent."""
    needed = bases(kind, role, piece)
    missing = [c for c in needed if rates.get(c) is None]
    if missing:
        raise MissingRateError(missing)
    lines = []
    for component, basis in needed.items():
        rate = rates[component]
        assert rate is not None
        lines.append(
            WageLine(
                component, basis, component_unit(kind, component), rate, to_paise(basis * rate)
            )
        )
    return WageResult(tuple(lines))
