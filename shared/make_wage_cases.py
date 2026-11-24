"""Regenerate shared/wage-cases.json from the hub's wage formulas.

The JSON is the contract between the hub (Python) and the app (TypeScript):
both test suites assert they produce exactly these numbers. Run from backend/:

    uv run python ../shared/make_wage_cases.py
"""

import json
from decimal import Decimal
from pathlib import Path

from fms.wages import MissingRateError, Piece, calculate_wage, perimeter

B, D, P, S = "block_cutting", "double_edge", "table_polish", "single_cutting"
BC = "block_cutter"  # paid per shift
SHIFT = {"sqft": "0", "rft": None}


def block(length, width):
    return {"sqft": str(Decimal(length) * Decimal(width)), "rft": None}


def true_size(length, width):  # double edge size that isn't in the table
    l, w = Decimal(length), Decimal(width)
    return {"sqft": str(l * w), "rft": str(perimeter(l, w))}


def table(rft, sqft):  # a size from the machine's size table
    return {"sqft": sqft, "rft": rft}


CASES = [
    # name, kind, role, piece, cuts, quantity, batti, rates
    ("cutting basic", B, "operator", block("2", "3"), 2, 5, None, {"cutting": "1.5"}),
    ("cutting decimals", B, "operator", block("1.1", "1.1"), 1, 1, None, {"cutting": "1"}),
    ("cutting 3dp sizes, 4dp rate", B, "operator", block("2.125", "1.875"), 3, 7, None,
     {"cutting": "1.2345"}),
    ("cutting rounds half up", B, "operator", block("0.5", "0.5"), 1, 1, None, {"cutting": "4.69"}),
    ("cutting zero cuts pays nothing", B, "operator", block("2", "2"), 0, 10, None,
     {"cutting": "1.5"}),
    ("cutting large batch", B, "operator", block("3", "2"), 3, 5000, None, {"cutting": "1.75"}),
    ("loading basic", B, "loader", block("2", "3"), 2, 5, None,
     {"loading": "0.5", "unloading": "0.25"}),
    ("loading zero cuts", B, "loader", block("2", "2"), 0, 1, None,
     {"loading": "1", "unloading": "1"}),
    ("loading decimals", B, "loader", block("2.5", "1.333"), 1, 9, None,
     {"loading": "0.333", "unloading": "0.1667"}),
    ("missing unloading rate", B, "loader", block("1", "1"), 1, 1, None,
     {"loading": "1", "unloading": None}),
    ("missing cutting rate", B, "operator", block("1", "1"), 1, 1, None, {"cutting": None}),
    # Owner's rate sheet
    ("double edge 2x2 operator", D, "operator", table("8", "4"), 0, 10, None, {"cutting": "0.22"}),
    ("double edge 2x1.5 operator", D, "operator", table("7", "3"), 0, 33, None,
     {"cutting": "0.22"}),
    ("double edge 2x1 loader", D, "loader", table("6", "2"), 0, 41, None, {"unloading": "0.15"}),
    ("double edge other size operator", D, "operator", true_size("1.25", "0.75"), 0, 7, None,
     {"cutting": "0.22"}),
    ("double edge other size loader", D, "loader", true_size("1.25", "0.75"), 0, 7, None,
     {"unloading": "0.15"}),
    ("single cutting 22.5 operator", S, "operator", table("8", "4"), 0, 25, None,
     {"cutting": "0.28"}),
    ("single cutting 9x9 loader", S, "loader", table("4", "1"), 0, 13, None,
     {"unloading": "0.15"}),
    ("single cutting 16x22 operator", S, "operator", table("7", "3"), 0, 3, None,
     {"cutting": "0.28"}),
    ("polish single batti", P, "operator", block("2", "1"), 0, 10, 1, {"polish_1": "0.45"}),
    ("polish double batti", P, "operator", block("1.5", "1.5"), 0, 7, 2, {"polish_2": "0.90"}),
    ("polish 4 batti", P, "operator", block("2", "2"), 0, 3, 4, {"polish_4": "1.10"}),
    ("polish 5 batti", P, "operator", block("2.25", "1.333"), 0, 11, 5, {"polish_5": "1.25"}),
    ("polish loader", P, "loader", block("2", "1.5"), 0, 9, 4, {"unloading": "0.15"}),
    ("polish missing batti rate", P, "operator", block("2", "2"), 0, 1, 3, {"polish_3": None}),
    ("block cutter shift", BC, "operator", SHIFT, 0, 1, None, {"shift": "450"}),
    ("block cutter odd shift rate", BC, "operator", SHIFT, 0, 1, None, {"shift": "333.333"}),
    ("block cutter missing rate", BC, "operator", SHIFT, 0, 1, None, {"shift": None}),
]


def main() -> None:
    out = []
    for name, kind, role, piece, cuts, qty, batti, rates in CASES:
        p = Piece(
            Decimal(piece["sqft"]),
            None if piece["rft"] is None else Decimal(piece["rft"]),
            cuts,
            qty,
            batti,
        )
        case = {
            "name": name,
            "kind": kind,
            "role": role,
            "piece_sqft": piece["sqft"],
            "piece_rft": piece["rft"],
            "cuts": cuts,
            "quantity": qty,
            "batti": batti,
            "rates": rates,
        }
        try:
            result = calculate_wage(
                kind, role, p, {k: None if v is None else Decimal(v) for k, v in rates.items()}
            )
            case["expected"] = {
                "lines": [{"component": ln.component, "amount": str(ln.amount)} for ln in result.lines],
                "total": str(result.total),
                "missing": [],
            }
        except MissingRateError as exc:
            case["expected"] = {"lines": [], "total": None, "missing": list(exc.components)}
        out.append(case)
    path = Path(__file__).with_name("wage-cases.json")
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(out)} cases to {path}")


if __name__ == "__main__":
    main()
