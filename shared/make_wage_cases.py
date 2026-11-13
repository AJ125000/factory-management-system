"""Regenerate shared/wage-cases.json from the hub's wage formulas.

The JSON is the contract between the hub (Python) and the app (TypeScript):
both test suites assert they produce exactly these numbers. Run from backend/:

    uv run python ../shared/make_wage_cases.py
"""

import json
from decimal import Decimal
from pathlib import Path

from fms.wages import MissingRateError, StoneEntry, calculate_wage

CASES = [
    # name, scheme, length, width, cuts, quantity, rates
    ("cutting basic", "cutting", "2", "3", 2, 5, {"cutting": "1.5"}),
    ("cutting decimals", "cutting", "1.1", "1.1", 1, 1, {"cutting": "1"}),
    ("cutting 3dp sizes, 4dp rate", "cutting", "2.125", "1.875", 3, 7, {"cutting": "1.2345"}),
    ("cutting rounds half up", "cutting", "0.5", "0.5", 1, 1, {"cutting": "4.69"}),
    ("cutting zero cuts pays nothing", "cutting", "2", "2", 0, 10, {"cutting": "1.5"}),
    ("cutting large batch", "cutting", "3", "2", 3, 5000, {"cutting": "1.75"}),
    ("loading basic", "loading", "2", "3", 2, 5, {"loading": "0.5", "unloading": "0.25"}),
    ("loading zero cuts", "loading", "2", "2", 0, 1, {"loading": "1", "unloading": "1"}),
    ("loading decimals", "loading", "2.5", "1.333", 1, 9, {"loading": "0.333", "unloading": "0.1667"}),
    ("missing unloading rate", "loading", "1", "1", 1, 1, {"loading": "1", "unloading": None}),
    ("missing cutting rate", "cutting", "1", "1", 1, 1, {"cutting": None}),
]


def main() -> None:
    out = []
    for name, scheme, length, width, cuts, qty, rates in CASES:
        entry = StoneEntry(Decimal(length), Decimal(width), cuts, qty)
        case = {
            "name": name,
            "scheme": scheme,
            "length_ft": length,
            "width_ft": width,
            "cuts": cuts,
            "quantity": qty,
            "rates": rates,
        }
        try:
            result = calculate_wage(
                scheme, entry, {k: None if v is None else Decimal(v) for k, v in rates.items()}
            )
            case["expected"] = {
                "lines": [
                    {"component": str(l.component), "amount": str(l.amount)} for l in result.lines
                ],
                "total": str(result.total),
                "missing": [],
            }
        except MissingRateError as exc:
            case["expected"] = {"lines": [], "total": None, "missing": [str(c) for c in exc.components]}
        out.append(case)
    path = Path(__file__).with_name("wage-cases.json")
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(out)} cases to {path}")


if __name__ == "__main__":
    main()
