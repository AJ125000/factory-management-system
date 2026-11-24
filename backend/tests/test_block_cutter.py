"""Block cutter machines (paid per shift) and the splitting machine's production columns."""

from __future__ import annotations

import io

import pytest
from openpyxl import load_workbook

from fms.services.machines import BLOCK_CUTTER_ID


@pytest.fixture
def op(api):
    return api.worker("Ramesh")


def _shift(api, worker, on, shift, status=201, **extra):
    body = {
        "worker_id": worker["id"],
        "machine_id": extra.pop("machine_id", BLOCK_CUTTER_ID),
        "entry_date": on,
        "shift": shift,
        **extra,
    }
    resp = api.c.post("/api/production", json=body)
    assert resp.status_code == status, resp.text
    return resp.json()


def _rate(api, value="450", effective_from="2026-01-01"):
    return api.rate("block_cutter", "shift", value, effective_from)


def test_block_cutter_pays_a_fixed_amount_per_shift(api, op):
    rate = _rate(api)
    assert rate["unit"] == "shift"
    day = _shift(api, op, "2026-03-02", "day")
    assert day["shift"] == "day" and day["quantity"] == 1
    assert day["wage"] == "450.00"
    assert day["wage_lines"] == [
        {"component": "shift", "basis": "1", "unit": "shift", "rate": "450", "amount": "450.00"}
    ]
    assert day["loader_worker_id"] is None and day["no_loader"] is False

    _shift(api, op, "2026-03-02", "night")  # a double shift
    report = api.wages("2026-03-01", "2026-03-31")
    (row,) = report["workers"]
    assert row["total_wage"] == "900.00"
    assert row["total_shifts"] == 2
    assert row["total_quantity"] == 0
    assert report["no_loader_entries"] == 0


def test_the_same_shift_cannot_be_entered_twice(api, op):
    _rate(api)
    _shift(api, op, "2026-03-02", "day")
    resp = _shift(api, op, "2026-03-02", "day", status=409)
    assert resp["error"]["details"]["reason"] == "duplicate_shift"
    second = api.ok(
        api.c.post("/api/machines", json={"kind": "block_cutter", "name_en": "Block cutter 2"}),
        201,
    )
    resp = _shift(api, op, "2026-03-02", "day", status=409, machine_id=second["id"])
    assert resp["error"]["details"]["reason"] == "duplicate_shift"
    other = api.worker("Mohan")
    _shift(api, other, "2026-03-02", "day")  # several workers on one shift


def test_shift_is_required_and_any_worker_can_work_it(api, op):
    _rate(api)
    resp = api.c.post(
        "/api/production",
        json={"worker_id": op["id"], "machine_id": BLOCK_CUTTER_ID, "entry_date": "2026-03-02"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["details"]["reason"] == "shift_required"
    raju = api.worker("Raju", "loader")
    entry = _shift(api, raju, "2026-03-02", "night")
    assert entry["wage"] == "450.00" and entry["paid_as"] == "operator"
    (row,) = api.wages("2026-03-01", "2026-03-31")["workers"]
    assert row["name_en"] == "Raju" and row["total_wage"] == "450.00"


def test_shift_rate_changes_keep_past_pay(api, op):
    _rate(api, "400", "2026-01-01")
    _rate(api, "500", "2026-03-01")
    assert _shift(api, op, "2026-02-27", "day")["wage"] == "400.00"
    assert _shift(api, op, "2026-03-02", "day")["wage"] == "500.00"


def test_block_cutter_has_no_loader(api, op):
    raju = api.worker("Raju", "loader")
    resp = api.c.post(
        "/api/loader-assignments",
        json={
            "machine_id": BLOCK_CUTTER_ID,
            "worker_id": raju["id"],
            "effective_from": "2026-01-01",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["details"]["reason"] == "machine_has_no_loader"
    _rate(api)
    entry = _shift(api, op, "2026-03-02", "day", loader_id=raju["id"])
    assert entry["loader_id"] is None
    assert len(api.wages("2026-03-01", "2026-03-31")["workers"]) == 1


def test_missing_shift_rate_is_flagged(api, op):
    entry = _shift(api, op, "2026-03-02", "day")
    assert entry["wage"] is None and entry["missing_rates"] == ["shift"]


def test_preview_and_editing_a_shift(api, op):
    _rate(api)
    preview = api.ok(
        api.c.post(
            "/api/production/preview",
            json={
                "worker_id": op["id"],
                "machine_id": BLOCK_CUTTER_ID,
                "entry_date": "2026-03-02",
                "shift": "night",
            },
        )
    )
    assert preview["wage"] == "450.00" and preview["no_loader"] is False
    day = _shift(api, op, "2026-03-02", "day")
    _shift(api, op, "2026-03-02", "night")
    clash = api.c.patch(f"/api/production/{day['id']}", json={"shift": "night"})
    assert clash.status_code == 409
    moved = api.ok(api.c.patch(f"/api/production/{day['id']}", json={"entry_date": "2026-03-01"}))
    assert moved["shift"] == "day" and moved["wage"] == "450.00"


def test_splitting_entries_show_machine_man_and_unloading_production(api, op):
    api.rate("block", "cutting", "1.5", "2026-01-01")
    # 2 x 3 ft, 2 cuts, 5 pieces: loading 30, machine man 2x6x2x5 = 120, unloading 6x3x5 = 90
    entry = api.entry(op, "2026-03-02")
    assert entry["area_sqft"] == "30"
    assert (entry["cutting_sqft"], entry["unloading_sqft"]) == ("120", "90")
    other = api.entry(op, "2026-03-02", machine="table_polish", batti=1)
    assert other["cutting_sqft"] is None and other["unloading_sqft"] is None


def test_excel_has_the_new_columns(api, op):
    api.rate("block", "cutting", "1.5", "2026-01-01")
    _rate(api)
    api.entry(op, "2026-03-02")
    _shift(api, op, "2026-03-03", "night")
    resp = api.c.get("/api/exports/wages.xlsx", params={"start": "2026-03-01", "end": "2026-03-31"})
    wb = load_workbook(io.BytesIO(resp.content))
    rows = [[c.value for c in r] for r in wb["Entries"].iter_rows() if any(c.value for c in r)]
    header, split, shift = rows[2], rows[3], rows[4]
    assert header[5] == "Shift" and header[10:12] == [
        "Machine man production (sq ft)",
        "Unloading production (sq ft)",
    ]
    assert (split[10], split[11]) == (120, 90)
    assert (shift[2], shift[5], shift[8], shift[13]) == (
        "Per shift",
        "Night",
        None,
        "Shift 450/shift",
    )
    wages = [[c.value for c in r] for r in wb["Wages"].iter_rows() if any(c.value for c in r)]
    assert wages[2][7] == "Shifts" and wages[3][7] == 1
