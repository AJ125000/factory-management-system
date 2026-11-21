from datetime import date
from decimal import Decimal as D

import pytest

from fms.services.machines import size_label
from fms.services.rates import RateBook
from fms.wages import (
    InvalidPieceError,
    MachineKind,
    MissingRateError,
    Piece,
    Role,
    Unit,
    allowed_components,
    calculate_wage,
    component_unit,
    to_paise,
)

BLOCK, DOUBLE, POLISH, SINGLE = (
    MachineKind.BLOCK_CUTTING,
    MachineKind.DOUBLE_EDGE,
    MachineKind.TABLE_POLISH,
    MachineKind.SINGLE_CUTTING,
)
OP, LOADER = Role.OPERATOR, Role.LOADER


def block_piece(length, width, cuts, quantity):
    return Piece(D(length) * D(width), None, cuts, quantity)


def test_block_cutting_formula():
    # 2 x (2 x 3 sq ft) x 2 cuts x 5 pieces = 120 sq ft effective, at 1.50 = 180.00
    result = calculate_wage(BLOCK, OP, block_piece("2", "3", 2, 5), {"cutting": D("1.5")})
    assert result.total == D("180.00")
    [line] = result.lines
    assert (line.basis, line.unit) == (D("120"), Unit.SQFT)


def test_block_loader_formula():
    # loading 6 x 5 = 30 sq ft at 0.50 = 15.00; unloading 6 x (1 + 2) x 5 = 90 sq ft at 0.25 = 22.50
    piece = block_piece("2", "3", 2, 5)
    result = calculate_wage(BLOCK, LOADER, piece, {"loading": D("0.5"), "unloading": D("0.25")})
    assert [(line.component, line.amount) for line in result.lines] == [
        ("loading", D("15.00")),
        ("unloading", D("22.50")),
    ]
    assert result.total == D("37.50")


def test_zero_cuts_still_pays_loading():
    piece = block_piece("2", "2", 0, 1)
    result = calculate_wage(BLOCK, LOADER, piece, {"loading": D("1"), "unloading": D("1")})
    assert result.total == D("8.00")  # 4 loading + 4 unloading


def test_decimal_precision_and_half_up_rounding():
    assert to_paise(D("2.345")) == D("2.35")
    result = calculate_wage(BLOCK, OP, block_piece("1.1", "1.1", 1, 1), {"cutting": D("1")})
    assert result.total == D("2.42")  # 2 x 1.21 = 2.42 exactly


def test_missing_rate_lists_components():
    with pytest.raises(MissingRateError) as exc:
        calculate_wage(
            BLOCK, LOADER, block_piece("1", "1", 1, 1), {"loading": D("1"), "unloading": None}
        )
    assert exc.value.components == ["unloading"]


# --------------------------------------------------------- owner's rate sheet
def test_double_edge_operator_paid_per_running_foot():
    # 2x2 ft = 8 running ft; 10 pieces x 8 x 0.22 = 17.60
    piece = Piece(D("4"), D("8"), 0, 10)
    result = calculate_wage(DOUBLE, OP, piece, {"cutting": D("0.22")})
    assert result.total == D("17.60")
    assert (result.lines[0].basis, result.lines[0].unit) == (D("80"), Unit.RFT)


def test_double_edge_loader_paid_per_sqft():
    # 2x2 ft = 4 sq ft; 10 pieces x 4 x 0.15 = 6.00
    result = calculate_wage(DOUBLE, LOADER, Piece(D("4"), D("8"), 0, 10), {"unloading": D("0.15")})
    assert result.total == D("6.00")


def test_single_cutting_uses_table_figures():
    # 22 1/2 x 22 1/2 in = 8 running ft / 4 sq ft (market standard); 25 pieces
    piece = Piece(D("4"), D("8"), 0, 25)
    assert calculate_wage(SINGLE, OP, piece, {"cutting": D("0.28")}).total == D("56.00")
    assert calculate_wage(SINGLE, LOADER, piece, {"unloading": D("0.15")}).total == D("15.00")


@pytest.mark.parametrize(
    ("batti", "rate", "expected"),
    [(1, "0.45", "9.00"), (2, "0.90", "18.00"), (4, "1.10", "22.00"), (5, "1.25", "25.00")],
)
def test_table_polish_rate_by_batti(batti, rate, expected):
    piece = Piece(D("2"), None, 0, 10, batti=batti)  # 2 x 1 ft, 10 pieces = 20 sq ft
    result = calculate_wage(POLISH, OP, piece, {f"polish_{batti}": D(rate)})
    assert result.total == D(expected)


def test_table_polish_missing_batti_rate():
    with pytest.raises(MissingRateError) as exc:
        calculate_wage(POLISH, OP, Piece(D("2"), None, 0, 1, batti=3), {"polish_4": D("1.10")})
    assert exc.value.components == ["polish_3"]


def test_table_polish_needs_batti():
    with pytest.raises(InvalidPieceError):
        calculate_wage(POLISH, OP, Piece(D("2"), None, 0, 1), {})


def test_components_and_units():
    assert allowed_components(BLOCK) == ("cutting", "loading", "unloading")
    assert allowed_components(SINGLE) == ("cutting", "unloading")
    assert "polish_5" in allowed_components(POLISH)
    assert component_unit(DOUBLE, "cutting") is Unit.RFT
    assert component_unit(BLOCK, "cutting") is Unit.SQFT
    assert component_unit(SINGLE, "unloading") is Unit.SQFT


def test_size_labels():
    assert size_label(D("22.5"), D("22.5")) == "22½ × 22½"
    assert size_label(D("2"), D("1.5")) == "2 × 1½"
    assert size_label(D("0.5"), D("2.25")) == "½ × 2.25"


class _Rate:
    def __init__(self, machine_id, component, value, effective_from):
        self.machine_id = machine_id
        self.component = component
        self.rate = D(value)
        self.effective_from = effective_from


def test_ratebook_uses_rate_in_effect_on_each_date():
    book = RateBook(
        [
            _Rate("m", "cutting", "2.0", date(2026, 2, 1)),  # inserted out of order on purpose
            _Rate("m", "cutting", "1.5", date(2026, 1, 1)),
        ]
    )
    assert book.lookup("m", "cutting", date(2025, 12, 31)) is None  # before any rate
    assert book.lookup("m", "cutting", date(2026, 1, 1)) == D("1.5")
    assert book.lookup("m", "cutting", date(2026, 1, 31)) == D("1.5")
    assert book.lookup("m", "cutting", date(2026, 2, 1)) == D("2.0")
    assert book.lookup("m", "cutting", date(2030, 1, 1)) == D("2.0")
    assert book.lookup("other", "cutting", date(2026, 6, 1)) is None
