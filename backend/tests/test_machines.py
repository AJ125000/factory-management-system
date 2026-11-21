"""Machines from the owner's rate sheet, size tables, and automatic loader pay."""

from decimal import Decimal

import pytest
import sqlalchemy as sa
from alembic import command
from conftest import MACHINES

from fms.db import alembic_config, make_engine, run_migrations


def _sizes(api, machine):
    sizes = api.ok(api.c.get("/api/machine-sizes", params={"machine_id": MACHINES[machine]}))
    return {(Decimal(s["length"]), Decimal(s["width"])): s for s in sizes}


def _size_id(api, machine, length, width):
    return _sizes(api, machine)[(Decimal(length), Decimal(width))]["id"]


@pytest.fixture
def op(api):
    return api.worker("Ramesh")


# ------------------------------------------------------------------ seeded data
def test_machines_and_sheet_are_set_up(api):
    machines = api.ok(api.c.get("/api/machines"))
    assert [m["kind"] for m in machines] == [
        "double_edge",
        "table_polish",
        "single_cutting",
        "block_cutting",
    ]
    assert machines[0]["name_hi"] == "डबल एज कटिंग मशीन"

    single = _sizes(api, "single_cutting")
    assert len(single) == 13
    figures = {k: (s["rft"], s["sqft"]) for k, s in single.items()}
    assert figures[(Decimal("21"), Decimal("21"))] == ("8", "4")  # owner's correction
    assert figures[(Decimal("22.5"), Decimal("22.5"))] == ("8", "4")
    assert figures[(Decimal("14"), Decimal("14"))] == ("6", "2")
    assert figures[(Decimal("11"), Decimal("22"))] == ("6", "2")
    double = _sizes(api, "double_edge")
    assert {k: (s["rft"], s["sqft"]) for k, s in double.items()} == {
        (Decimal("2"), Decimal("2")): ("8", "4"),
        (Decimal("2"), Decimal("1.5")): ("7", "3"),
        (Decimal("2"), Decimal("1")): ("6", "2"),
    }

    current = api.ok(api.c.get("/api/rates/current", params={"on": "2026-06-01"}))
    by = {(r["machine_id"], r["component"]): (r["rate"], r["unit"]) for r in current}
    assert by[(MACHINES["double_edge"], "cutting")] == ("0.22", "rft")
    assert by[(MACHINES["single_cutting"], "cutting")] == ("0.28", "rft")
    assert by[(MACHINES["table_polish"], "polish_1")] == ("0.45", "sqft")
    assert by[(MACHINES["table_polish"], "polish_2")] == ("0.90", "sqft")
    assert by[(MACHINES["table_polish"], "polish_4")] == ("1.10", "sqft")
    assert by[(MACHINES["table_polish"], "polish_5")] == ("1.25", "sqft")
    assert (MACHINES["table_polish"], "polish_3") not in by  # no 3-batti rate on the sheet
    for machine in ("double_edge", "table_polish", "single_cutting"):
        assert by[(MACHINES[machine], "unloading")] == ("0.15", "sqft")


# --------------------------------------------------------------- operator pay
def test_double_edge_uses_table_sizes_either_way_round(api, op):
    e = api.entry(op, "2026-03-02", "1.5", "2", cuts=0, quantity=10, machine="double_edge")
    assert (e["piece_rft"], e["piece_sqft"], e["size_label"]) == ("7", "3", "2 × 1½")
    assert e["wage"] == "15.40"  # 10 x 7 running ft x 0.22
    assert e["wage_lines"][0]["unit"] == "rft"
    assert e["size_id"] == _size_id(api, "double_edge", "2", "1.5")


def test_double_edge_other_sizes_use_true_perimeter_and_area(api, op):
    e = api.entry(op, "2026-03-02", "1.25", "0.75", cuts=0, quantity=4, machine="double_edge")
    assert (e["piece_rft"], e["piece_sqft"], e["size_id"]) == ("4", "0.9375", None)
    assert e["wage"] == "3.52"  # 4 pieces x 4 running ft x 0.22
    assert e["loader_wage"] == "0.56"  # 3.75 sq ft x 0.15 = 0.5625


def test_single_cutting_needs_a_size_from_the_table(api, op):
    body = {
        "worker_id": op["id"],
        "machine_id": MACHINES["single_cutting"],
        "entry_date": "2026-03-02",
        "quantity": 25,
    }
    missing = api.c.post("/api/production", json=body)
    assert missing.json()["error"]["details"]["reason"] == "size_required"
    other_machine = api.c.post(
        "/api/production", json={**body, "size_id": _size_id(api, "double_edge", "2", "2")}
    )
    assert other_machine.json()["error"]["details"]["reason"] == "unknown_size"

    size = _size_id(api, "single_cutting", "22.5", "22.5")
    e = api.ok(api.c.post("/api/production", json={**body, "size_id": size}), 201)
    assert (e["size_label"], e["piece_rft"], e["piece_sqft"]) == ("22½ × 22½", "8", "4")
    assert (e["length_ft"], e["width_ft"]) == (None, None)
    assert e["wage"] == "56.00"  # 25 x 8 x 0.28
    assert e["loader_wage"] == "15.00"  # 25 x 4 x 0.15


def test_table_polish_rate_depends_on_batti(api, op):
    no_batti = api.c.post(
        "/api/production",
        json={
            "worker_id": op["id"],
            "machine_id": MACHINES["table_polish"],
            "entry_date": "2026-03-02",
            "length_ft": "2",
            "width_ft": "1",
            "quantity": 10,
        },
    )
    assert no_batti.json()["error"]["details"]["reason"] == "batti_required"
    four = api.entry(
        op, "2026-03-02", "2", "1", cuts=0, quantity=10, machine="table_polish", batti=4
    )
    assert four["wage"] == "22.00"  # 20 sq ft x 1.10
    assert four["wage_lines"][0]["component"] == "polish_4"
    three = api.entry(
        op, "2026-03-02", "2", "1", cuts=0, quantity=1, machine="table_polish", batti=3
    )
    assert three["wage"] is None and three["missing_rates"] == ["polish_3"]


def test_operators_move_between_machines(api, op):
    api.entry(op, "2026-03-02", "2", "2", cuts=0, quantity=10, machine="double_edge")  # 17.60
    api.entry(op, "2026-03-02", "2", "1", cuts=0, quantity=10, machine="table_polish", batti=1)
    report = api.wages("2026-03-01", "2026-03-31")
    [row] = report["workers"]
    assert row["total_wage"] == "26.60"  # 17.60 + 20 sq ft x 0.45
    assert row["total_rft"] == "80.00"


def test_editing_the_size_table_keeps_saved_entries(api, op):
    size = _size_id(api, "single_cutting", "14", "14")
    body = {
        "worker_id": op["id"],
        "machine_id": MACHINES["single_cutting"],
        "entry_date": "2026-03-02",
        "size_id": size,
        "quantity": 10,
    }
    e = api.ok(api.c.post("/api/production", json=body), 201)
    assert e["wage"] == "16.80"  # 10 x 6 x 0.28
    api.ok(api.c.patch(f"/api/machine-sizes/{size}", json={"rft": "5"}))
    # A later edit that doesn't change the size keeps the figures it was saved with.
    edited = api.ok(api.c.patch(f"/api/production/{e['id']}", json={**body, "quantity": 20}))
    assert (edited["piece_rft"], edited["wage"]) == ("6", "33.60")
    new = api.ok(api.c.post("/api/production", json=body), 201)
    assert new["wage"] == "14.00"  # 10 x 5 x 0.28


def test_owner_adds_a_size(api, op):
    created = api.ok(
        api.c.post(
            "/api/machine-sizes",
            json={
                "machine_id": MACHINES["single_cutting"],
                "length": "12",
                "width": "12",
                "rft": "5",
                "sqft": "1",
            },
        ),
        201,
    )
    dup = api.c.post(
        "/api/machine-sizes",
        json={
            "machine_id": MACHINES["single_cutting"],
            "length": "22",
            "width": "16",
            "rft": "1",
            "sqft": "1",
        },
    )
    assert dup.status_code == 409  # 16 x 22 is already there
    no_table = api.c.post(
        "/api/machine-sizes",
        json={
            "machine_id": MACHINES["table_polish"],
            "length": "1",
            "width": "1",
            "rft": "1",
            "sqft": "1",
        },
    )
    assert no_table.json()["error"]["details"]["reason"] == "no_size_table"
    e = api.ok(
        api.c.post(
            "/api/production",
            json={
                "worker_id": op["id"],
                "machine_id": MACHINES["single_cutting"],
                "entry_date": "2026-03-02",
                "size_id": created["id"],
                "quantity": 2,
            },
        ),
        201,
    )
    assert e["wage"] == "2.80"


# ----------------------------------------------------------------- loader pay
def test_loader_is_paid_from_operator_entries(api, op):
    raju = api.worker("Raju", "loader")
    api.assign("single_cutting", raju, "2026-01-01")
    size = _size_id(api, "single_cutting", "16", "22")
    api.entry(op, "2026-03-02", machine="single_cutting", size_id=size, quantity=20)

    report = api.wages("2026-03-01", "2026-03-31", include_entries=True)
    raju_row, ramesh = report["workers"]  # sorted by name
    assert (ramesh["total_wage"], raju_row["total_wage"]) == ("39.20", "9.00")  # 20x7x.28, 20x3x.15
    assert raju_row["entries"][0]["paid_as"] == "loader"
    assert (ramesh["total_rft"], raju_row["total_rft"]) == ("140.00", "0.00")
    assert raju_row["entries"][0]["wage_lines"][0]["basis"] == "60"
    assert report["total_wage"] == "48.20"
    assert report["no_loader_entries"] == 0


def test_loaders_cannot_have_their_own_entries(api):
    raju = api.worker("Raju", "loader")
    resp = api.c.post(
        "/api/production",
        json={
            "worker_id": raju["id"],
            "entry_date": "2026-03-02",
            "length_ft": "2",
            "width_ft": "2",
            "quantity": 1,
        },
    )
    assert resp.json()["error"]["details"]["reason"] == "loader_paid_automatically"


def test_swapping_loaders_keeps_past_pay(api, op):
    raju, shyam = api.worker("Raju", "loader"), api.worker("Shyam", "loader")
    api.assign("double_edge", raju, "2026-03-01")
    api.assign("table_polish", shyam, "2026-03-01")
    api.entry(op, "2026-03-05", "2", "2", cuts=0, quantity=10, machine="double_edge")  # Raju 6.00
    # Swap them from the 10th.
    api.assign("double_edge", shyam, "2026-03-10")
    api.assign("table_polish", raju, "2026-03-10")
    api.entry(op, "2026-03-12", "2", "2", cuts=0, quantity=10, machine="double_edge")  # Shyam 6.00
    api.entry(op, "2026-03-12", "2", "1", cuts=0, quantity=10, machine="table_polish", batti=2)

    pay = {r["name_en"]: r["total_wage"] for r in api.wages("2026-03-01", "2026-03-31")["workers"]}
    assert pay == {"Ramesh": "53.20", "Raju": "9.00", "Shyam": "6.00"}  # Raju 6.00 + 3.00


def test_one_loader_can_cover_two_machines(api, op):
    raju = api.worker("Raju", "loader")
    api.assign("double_edge", raju, "2026-03-01")
    api.assign("single_cutting", raju, "2026-03-01")
    api.entry(op, "2026-03-05", "2", "2", cuts=0, quantity=10, machine="double_edge")
    api.entry(
        op,
        "2026-03-05",
        machine="single_cutting",
        quantity=10,
        size_id=_size_id(api, "single_cutting", "9", "9"),
    )
    [row] = api.wages("2026-03-01", "2026-03-31", worker_id=raju["id"])["workers"]
    assert row["total_wage"] == "7.50"  # 40 x 0.15 + 10 x 0.15


def test_filling_in_for_an_absent_loader(api, op):
    raju, shyam = api.worker("Raju", "loader"), api.worker("Shyam", "loader")
    api.assign("double_edge", raju, "2026-03-01")
    e = api.entry(
        op,
        "2026-03-05",
        "2",
        "2",
        cuts=0,
        quantity=10,
        machine="double_edge",
        loader_id=shyam["id"],
    )
    assert e["loader_worker_id"] == shyam["id"]
    pay = {r["name_en"]: r["total_wage"] for r in api.wages("2026-03-01", "2026-03-31")["workers"]}
    assert pay == {"Ramesh": "17.60", "Shyam": "6.00"}
    # Undo: back to the usual loader.
    back = api.ok(api.c.patch(f"/api/production/{e['id']}", json={"loader_id": None}))
    assert back["loader_worker_id"] == raju["id"]

    not_loader = api.c.post(
        "/api/production",
        json={
            "worker_id": op["id"],
            "machine_id": MACHINES["double_edge"],
            "entry_date": "2026-03-05",
            "length_ft": "2",
            "width_ft": "2",
            "quantity": 1,
            "loader_id": op["id"],
        },
    )
    assert not_loader.json()["error"]["details"]["reason"] == "not_a_loader"


def test_no_loader_is_saved_and_flagged(api, op):
    e = api.entry(op, "2026-03-05", "2", "2", cuts=0, quantity=10, machine="double_edge")
    assert e["no_loader"] is True and e["loader_worker_id"] is None
    report = api.wages("2026-03-01", "2026-03-31")
    assert report["no_loader_entries"] == 1
    assert report["total_wage"] == "17.60"  # nobody was paid for loading


def test_assignment_rules(api, op):
    raju = api.worker("Raju", "loader")
    bad = api.c.post(
        "/api/loader-assignments",
        json={
            "machine_id": MACHINES["double_edge"],
            "worker_id": op["id"],
            "effective_from": "2026-03-01",
        },
    )
    assert bad.json()["error"]["details"]["reason"] == "not_a_loader"
    api.assign("double_edge", raju, "2026-03-01")
    dup = api.c.post(
        "/api/loader-assignments",
        json={
            "machine_id": MACHINES["double_edge"],
            "worker_id": None,
            "effective_from": "2026-03-01",
        },
    )
    assert dup.status_code == 409


def test_deleting_a_loader_does_not_pay_the_previous_one(api, op):
    old, new = api.worker("Old", "loader"), api.worker("New", "loader")
    api.assign("double_edge", old, "2026-03-01")
    api.assign("double_edge", new, "2026-03-10")
    api.entry(op, "2026-03-12", "2", "2", cuts=0, quantity=10, machine="double_edge")
    impact = api.ok(api.c.get(f"/api/workers/{new['id']}/delete-impact"))
    assert impact == {"worker_id": new["id"], "production_entries": 0, "loader_assignments": 1}
    api.ok(api.c.delete(f"/api/workers/{new['id']}", params={"confirm_entries": 0}), 204)
    report = api.wages("2026-03-01", "2026-03-31")
    assert [r["name_en"] for r in report["workers"]] == ["Ramesh"]
    assert report["no_loader_entries"] == 1


def test_preview_shows_loader_pay(api, op):
    raju = api.worker("Raju", "loader")
    api.assign("double_edge", raju, "2026-03-01")
    preview = api.ok(
        api.c.post(
            "/api/production/preview",
            json={
                "worker_id": op["id"],
                "machine_id": MACHINES["double_edge"],
                "entry_date": "2026-03-05",
                "length_ft": "2",
                "width_ft": "1",
                "quantity": 10,
            },
        )
    )
    assert (preview["wage"], preview["loader_wage"]) == ("13.20", "3.00")
    assert preview["loader_worker_id"] == raju["id"]
    assert (preview["rft_total"], preview["area_sqft"]) == ("60", "20")
    assert api.ok(api.c.get("/api/production"))["total"] == 0


def test_inactive_machine_takes_no_new_entries(api, op):
    renamed = api.ok(
        api.c.patch(
            f"/api/machines/{MACHINES['block']}",
            json={"name_en": "Block cutter", "name_hi": "ब्लॉक कटर", "is_active": False},
        )
    )
    assert renamed["name_en"] == "Block cutter"
    resp = api.c.post(
        "/api/production",
        json={
            "worker_id": op["id"],
            "entry_date": "2026-03-02",
            "length_ft": "2",
            "width_ft": "2",
            "cuts": 1,
            "quantity": 1,
        },
    )
    assert resp.json()["error"]["details"]["reason"] == "machine_inactive"


def test_moving_an_entry_to_another_machine(api, op):
    e = api.entry(op, "2026-03-02", "2", "2", cuts=0, quantity=10, machine="double_edge")
    size = _size_id(api, "single_cutting", "22", "22")
    moved = api.ok(
        api.c.patch(
            f"/api/production/{e['id']}",
            json={"machine_id": MACHINES["single_cutting"], "size_id": size},
        )
    )
    assert (moved["machine_id"], moved["size_label"], moved["length_ft"]) == (
        MACHINES["single_cutting"],
        "22 × 22",
        None,
    )
    assert moved["wage"] == "22.40"  # 10 x 8 x 0.28
    resized = api.ok(
        api.c.patch(
            f"/api/production/{e['id']}",
            json={"machine_id": MACHINES["double_edge"], "length_ft": "2", "width_ft": "1"},
        )
    )
    assert (resized["piece_rft"], resized["size_label"]) == ("6", "2 × 1")


# ------------------------------------------------------------------ upgrading
def test_upgrade_keeps_existing_data(tmp_path):
    """A laptop already running 0.5 keeps its workers, rates and entries."""
    url = f"sqlite:///{(tmp_path / 'old.db').as_posix()}"
    engine = make_engine(url, foreign_keys=False)
    cfg = alembic_config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "0002")
        op_type, loader_type = (
            "00000000-0000-4000-8000-000000000001",
            "00000000-0000-4000-8000-000000000002",
        )
        conn.execute(
            sa.text(
                "INSERT INTO workers (id, name_en, worker_type_id, created_at, updated_at) "
                "VALUES ('w1', 'Ramesh', :t, '2026-01-01', '2026-01-01')"
            ),
            {"t": op_type},
        )
        conn.execute(
            sa.text(
                "INSERT INTO rates (id, worker_type_id, component, rate_per_sqft, effective_from, "
                "created_at, updated_at) VALUES ('r1', :t, 'cutting', '1.5', '2026-01-01', "
                "'2026-01-01', '2026-01-01'), ('r2', :l, 'loading', '0.5', '2026-01-01', "
                "'2026-01-01', '2026-01-01')"
            ),
            {"t": op_type, "l": loader_type},
        )
        conn.execute(
            sa.text(
                "INSERT INTO production_entries (id, worker_id, worker_type_id, entry_date, "
                "length_ft, width_ft, cuts, quantity, created_at, updated_at) "
                "VALUES ('e1', 'w1', :t, '2026-02-01', '2.5', '1.5', 2, 5, "
                "'2026-02-01', '2026-02-01')"
            ),
            {"t": op_type},
        )
    engine.dispose()

    run_migrations(url)
    engine = make_engine(url)
    with engine.connect() as conn:
        entry = conn.execute(
            sa.text("SELECT machine_id, piece_sqft, piece_rft FROM production_entries")
        ).one()
        rates = conn.execute(
            sa.text(
                "SELECT component, rate, machine_id FROM rates WHERE id IN ('r1', 'r2') ORDER BY id"
            )
        ).all()
        roles = dict(conn.execute(sa.text("SELECT code, role FROM worker_types")).all())
    engine.dispose()
    assert entry == (MACHINES["block"], "3.75", None)
    assert rates == [("cutting", "1.5", MACHINES["block"]), ("loading", "0.5", MACHINES["block"])]
    assert roles == {"machine_operator": "operator", "loader": "loader"}
