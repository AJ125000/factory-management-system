from datetime import date, timedelta


def test_rate_component_must_match_worker_type(api):
    resp = api.c.post(
        "/api/rates",
        json={
            "worker_type_id": api.type_id["machine_operator"],
            "component": "loading",
            "rate_per_sqft": "1",
            "effective_from": "2026-01-01",
        },
    )
    assert resp.status_code == 422


def test_duplicate_effective_date_conflicts(api):
    api.rate("loader", "loading", "0.5", "2026-01-01")
    resp = api.c.post(
        "/api/rates",
        json={
            "worker_type_id": api.type_id["loader"],
            "component": "loading",
            "rate_per_sqft": "0.6",
            "effective_from": "2026-01-01",
        },
    )
    assert resp.status_code == 409


def test_current_rates(api):
    api.rate("machine_operator", "cutting", "1.5", "2026-01-01")
    api.rate("machine_operator", "cutting", "2", "2026-03-01")
    current = api.ok(api.c.get("/api/rates/current", params={"on": "2026-02-15"}))
    cutting = next(r for r in current if r["component"] == "cutting")
    assert cutting["rate_per_sqft"] == "1.5"
    assert cutting["effective_from"] == "2026-01-01"
    loading = next(r for r in current if r["component"] == "loading")
    assert loading["rate_per_sqft"] is None


def test_rate_increase_does_not_change_past_wages(api):
    w = api.worker("Ramesh")
    api.rate("machine_operator", "cutting", "1.5", "2026-01-01")
    api.entry(w, "2026-01-20")  # 120 sq ft effective -> 180.00 at 1.5
    before = api.wages("2026-01-01", "2026-01-31")["total_wage"]

    api.rate("machine_operator", "cutting", "2", "2026-02-01")  # raise from February
    api.entry(w, "2026-02-03")  # -> 240.00 at 2.0

    assert api.wages("2026-01-01", "2026-01-31")["total_wage"] == before == "180.00"
    both = api.wages("2026-01-01", "2026-02-28")
    assert both["total_wage"] == "420.00"


def test_changing_worker_type_keeps_past_wages(api):
    w = api.worker("Dinesh", "loader")
    api.rate("loader", "loading", "0.5", "2026-01-01")
    api.rate("loader", "unloading", "0.25", "2026-01-01")
    api.rate("machine_operator", "cutting", "1.5", "2026-01-01")
    api.entry(w, "2026-01-10")  # loader: 37.50

    api.ok(
        api.c.patch(
            f"/api/workers/{w['id']}", json={"worker_type_id": api.type_id["machine_operator"]}
        )
    )
    api.entry(w, "2026-01-11")  # now operator: 180.00

    report = api.wages("2026-01-01", "2026-01-31", include_entries=True)
    [row] = report["workers"]
    assert [e["wage"] for e in row["entries"]] == ["37.50", "180.00"]
    assert row["total_wage"] == "217.50"


def test_wages_report_totals_and_breakdown(api):
    a = api.worker("Amit", name_hi="अमित")
    b = api.worker("Bharat", "loader")
    api.rate("machine_operator", "cutting", "1.5", "2026-01-01")
    api.rate("loader", "loading", "0.5", "2026-01-01")
    api.rate("loader", "unloading", "0.25", "2026-01-01")
    api.entry(a, "2026-01-02")
    api.entry(
        a, "2026-01-03", length="1.5", width="1", cuts=1, quantity=10
    )  # 2*1.5*1*10 = 30 -> 45.00
    api.entry(b, "2026-01-02")
    api.entry(a, "2026-02-01")  # outside the period

    report = api.wages("2026-01-01", "2026-01-31", include_entries=True)
    amit, bharat = report["workers"]
    assert amit["name_hi"] == "अमित"
    assert amit["entry_count"] == 2
    assert amit["total_wage"] == "225.00"
    assert amit["total_area_sqft"] == "45.00"  # 6*5 + 1.5*10
    assert amit["total_cuts"] == 20  # 2*5 + 1*10
    assert bharat["total_wage"] == "37.50"
    assert report["total_wage"] == "262.50"
    line = bharat["entries"][0]["wage_lines"][1]
    assert line == {
        "component": "unloading",
        "effective_area_sqft": "90",
        "rate_per_sqft": "0.25",
        "amount": "22.50",
    }

    only_bharat = api.wages("2026-01-01", "2026-01-31", worker_id=b["id"])
    assert [r["name_en"] for r in only_bharat["workers"]] == ["Bharat"]


def test_missing_rates_are_flagged_not_hidden(api):
    w = api.worker("Kamal")
    api.rate("machine_operator", "cutting", "1.5", "2026-02-01")
    entry = api.entry(w, "2026-01-15")  # before any rate existed
    assert entry["wage"] is None
    assert entry["missing_rates"] == ["cutting"]
    report = api.wages("2026-01-01", "2026-01-31")
    assert report["missing_rate_entries"] == 1
    assert report["workers"][0]["total_wage"] == "0.00"


def test_production_summary_by_month_and_year(api):
    w = api.worker("Amit")
    api.rate("machine_operator", "cutting", "1", "2025-01-01")
    api.entry(w, "2025-12-31")
    api.entry(w, "2026-01-01")
    api.entry(w, "2026-01-15")

    monthly = api.ok(
        api.c.get(
            "/api/reports/production",
            params={"start": "2025-01-01", "end": "2026-12-31", "group_by": "month"},
        )
    )
    assert [(b["period"], b["entry_count"]) for b in monthly["buckets"]] == [
        ("2025-12", 1),
        ("2026-01", 2),
    ]
    assert monthly["totals"]["total_area_sqft"] == "90.00"
    assert monthly["totals"]["total_wage"] == "360.00"

    yearly = api.ok(
        api.c.get(
            "/api/reports/production",
            params={"start": "2025-01-01", "end": "2026-12-31", "group_by": "year"},
        )
    )
    assert [b["period"] for b in yearly["buckets"]] == ["2025", "2026"]


def test_production_validation(api):
    w = api.worker("Amit")
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    future = api.c.post(
        "/api/production",
        json={
            "worker_id": w["id"],
            "entry_date": tomorrow,
            "length_ft": "1",
            "width_ft": "1",
            "cuts": 1,
            "quantity": 1,
        },
    )
    assert future.status_code == 422
    negative = api.c.post(
        "/api/production",
        json={
            "worker_id": w["id"],
            "entry_date": "2026-01-01",
            "length_ft": "-1",
            "width_ft": "1",
            "cuts": 1,
            "quantity": 1,
        },
    )
    assert negative.status_code == 422
    bad_period = api.c.get(
        "/api/reports/wages", params={"start": "2026-02-01", "end": "2026-01-01"}
    )
    assert bad_period.status_code == 422


def test_edit_and_delete_entry(api):
    w = api.worker("Amit")
    api.rate("machine_operator", "cutting", "1.5", "2026-01-01")
    e = api.entry(w, "2026-01-05")
    edited = api.ok(api.c.patch(f"/api/production/{e['id']}", json={"quantity": 10}))
    assert edited["wage"] == "360.00"
    api.ok(api.c.delete(f"/api/production/{e['id']}"), 204)
    assert api.ok(api.c.get("/api/production"))["total"] == 0
