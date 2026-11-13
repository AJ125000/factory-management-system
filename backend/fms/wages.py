"""Wage formulas - pure functions with no database access.

All measurements are in feet and square feet, all rates in rupees per square foot.
Money uses Decimal (never float). Each wage line is rounded to the paisa (half-up),
and an entry's total is the sum of its rounded lines.

Formulas (carried over from the prototype; the 2 x in cutting confirmed by the owner, Nov 2026):

* Cutting (machine operator):
      2 x piece_area x cuts x quantity x cutting_rate
* Loading (loader):
      loading   = piece_area x quantity x loading_rate
      unloading = piece_area x (1 + cuts) x quantity x unloading_rate
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


class PayScheme(StrEnum):
    CUTTING = "cutting"
    LOADING = "loading"


class RateComponent(StrEnum):
    CUTTING = "cutting"
    LOADING = "loading"
    UNLOADING = "unloading"


SCHEME_COMPONENTS: dict[PayScheme, tuple[RateComponent, ...]] = {
    PayScheme.CUTTING: (RateComponent.CUTTING,),
    PayScheme.LOADING: (RateComponent.LOADING, RateComponent.UNLOADING),
}

PAISA = Decimal("0.01")
ZERO = Decimal("0.00")


def to_paise(amount: Decimal) -> Decimal:
    return amount.quantize(PAISA, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class StoneEntry:
    length_ft: Decimal
    width_ft: Decimal
    cuts: int
    quantity: int

    @property
    def piece_area(self) -> Decimal:
        return self.length_ft * self.width_ft

    @property
    def total_area(self) -> Decimal:
        return self.piece_area * self.quantity


@dataclass(frozen=True)
class WageLine:
    component: RateComponent
    effective_area: Decimal
    rate: Decimal
    amount: Decimal


@dataclass(frozen=True)
class WageResult:
    lines: tuple[WageLine, ...]

    @property
    def total(self) -> Decimal:
        return sum((line.amount for line in self.lines), ZERO)


class MissingRateError(Exception):
    def __init__(self, components: list[RateComponent]) -> None:
        super().__init__(f"No rate set for: {', '.join(components)}")
        self.components = components


def effective_areas(scheme: PayScheme | str, entry: StoneEntry) -> dict[RateComponent, Decimal]:
    """The area each rate component is multiplied by."""
    scheme = PayScheme(scheme)
    area, qty = entry.piece_area, entry.quantity
    if scheme is PayScheme.CUTTING:
        return {RateComponent.CUTTING: 2 * area * entry.cuts * qty}
    return {
        RateComponent.LOADING: area * qty,
        RateComponent.UNLOADING: area * (1 + entry.cuts) * qty,
    }


def calculate_wage(
    scheme: PayScheme | str,
    entry: StoneEntry,
    rates: Mapping[RateComponent, Decimal | None],
) -> WageResult:
    """Wage for one production entry. Raises MissingRateError if a needed rate is absent."""
    areas = effective_areas(scheme, entry)
    missing = [c for c in areas if rates.get(c) is None]
    if missing:
        raise MissingRateError(missing)
    lines = []
    for component, area in areas.items():
        rate = rates[component]
        assert rate is not None
        lines.append(WageLine(component, area, rate, to_paise(area * rate)))
    return WageResult(tuple(lines))
