from datetime import date
from decimal import Decimal as D

import pytest

from fms.services.rates import RateBook
from fms.wages import (
    MissingRateError,
    PayScheme,
    RateComponent,
    StoneEntry,
    calculate_wage,
    to_paise,
)

C = RateComponent


def test_cutting_formula():
    # 2 x (2 x 3 sq ft) x 2 cuts x 5 pieces = 120 sq ft effective, at 1.50 = 180.00
    entry = StoneEntry(D("2"), D("3"), cuts=2, quantity=5)
    result = calculate_wage(PayScheme.CUTTING, entry, {C.CUTTING: D("1.5")})
    assert result.total == D("180.00")
    [line] = result.lines
    assert line.effective_area == D("120")


def test_loading_formula():
    # loading 6 x 5 = 30 sq ft at 0.50 = 15.00; unloading 6 x (1 + 2) x 5 = 90 sq ft at 0.25 = 22.50
    entry = StoneEntry(D("2"), D("3"), cuts=2, quantity=5)
    result = calculate_wage("loading", entry, {C.LOADING: D("0.5"), C.UNLOADING: D("0.25")})
    assert [(line.component, line.amount) for line in result.lines] == [
        (C.LOADING, D("15.00")),
        (C.UNLOADING, D("22.50")),
    ]
    assert result.total == D("37.50")


def test_zero_cuts_still_pays_loading():
    entry = StoneEntry(D("2"), D("2"), cuts=0, quantity=1)
    result = calculate_wage("loading", entry, {C.LOADING: D("1"), C.UNLOADING: D("1")})
    assert result.total == D("8.00")  # 4 loading + 4 unloading


def test_decimal_precision_and_half_up_rounding():
    # 0.1 + 0.2 style float errors must not appear; 2.345 rounds up to 2.35
    assert to_paise(D("2.345")) == D("2.35")
    entry = StoneEntry(D("1.1"), D("1.1"), cuts=1, quantity=1)
    result = calculate_wage("cutting", entry, {C.CUTTING: D("1")})
    assert result.total == D("2.42")  # 2 x 1.21 = 2.42 exactly


def test_missing_rate_lists_components():
    entry = StoneEntry(D("1"), D("1"), cuts=1, quantity=1)
    with pytest.raises(MissingRateError) as exc:
        calculate_wage("loading", entry, {C.LOADING: D("1"), C.UNLOADING: None})
    assert exc.value.components == [C.UNLOADING]


class _Rate:
    def __init__(self, type_id, component, value, effective_from):
        self.worker_type_id = type_id
        self.component = component
        self.rate_per_sqft = D(value)
        self.effective_from = effective_from


def test_ratebook_uses_rate_in_effect_on_each_date():
    book = RateBook(
        [
            _Rate("op", "cutting", "2.0", date(2026, 2, 1)),  # inserted out of order on purpose
            _Rate("op", "cutting", "1.5", date(2026, 1, 1)),
        ]
    )
    assert book.lookup("op", C.CUTTING, date(2025, 12, 31)) is None  # before any rate
    assert book.lookup("op", C.CUTTING, date(2026, 1, 1)) == D("1.5")
    assert book.lookup("op", C.CUTTING, date(2026, 1, 31)) == D("1.5")
    assert book.lookup("op", C.CUTTING, date(2026, 2, 1)) == D("2.0")
    assert book.lookup("op", C.CUTTING, date(2030, 1, 1)) == D("2.0")
    assert book.lookup("other", C.CUTTING, date(2026, 6, 1)) is None
