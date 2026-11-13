from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from fms.config import Settings
from fms.main import create_app


def _seed(api):
    a = api.worker("Ramesh", name_hi="रमेश")
    b = api.worker("Suresh", "loader", name_hi="सुरेश")
    api.rate("machine_operator", "cutting", "1.5", "2026-01-01")
    api.rate("loader", "loading", "0.5", "2026-01-01")
    api.rate("loader", "unloading", "0.25", "2026-01-01")
    api.entry(a, "2026-01-05")  # 180.00
    api.entry(a, "2026-02-03")  # 180.00
    api.entry(b, "2026-01-06")  # 37.50
    return a, b


def _xlsx(api, path, **params):
    resp = api.c.get(path, params=params)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml"
    )
    assert "attachment" in resp.headers["content-disposition"]
    return load_workbook(BytesIO(resp.content))


def _rows(ws):
    return [[c.value for c in row] for row in ws.iter_rows() if any(c.value for c in row)]


def test_wages_excel_in_english(api):
    _seed(api)
    wb = _xlsx(api, "/api/exports/wages.xlsx", start="2026-01-01", end="2026-01-31")
    assert wb.sheetnames == ["Wages", "Entries"]

    rows = _rows(wb["Wages"])
    assert rows[0][0] == "Kota Stone Factory"
    header = rows[2]
    assert header[0] == "Worker" and header[6] == "Wages (₹)"
    ramesh, suresh, total = rows[3], rows[4], rows[5]
    assert ramesh[:2] == ["Ramesh", "Machine Operator"]
    assert Decimal(str(ramesh[6])) == Decimal("180")  # a real number, not text
    assert suresh[0] == "Suresh"
    assert total[0] == "Total" and Decimal(str(total[6])) == Decimal("217.5")

    entries = _rows(wb["Entries"])
    first = entries[3]
    assert first[0].date() == date(2026, 1, 5)  # a real date cell
    assert first[8] == "Cutting 1.5"


def test_wages_excel_in_hindi(api):
    _seed(api)
    api.ok(api.c.patch("/api/settings", json={"factory_name_hi": "श्री गणेश स्टोन"}))
    wb = _xlsx(api, "/api/exports/wages.xlsx", start="2026-01-01", end="2026-01-31", lang="hi")
    assert wb.sheetnames == ["मज़दूरी", "एंट्रियाँ"]
    rows = _rows(wb["मज़दूरी"])
    assert rows[0][0] == "श्री गणेश स्टोन"
    assert rows[2][0] == "मज़दूर"
    assert rows[3][:2] == ["रमेश", "मशीन ऑपरेटर"]
    loader_entry = [r for r in _rows(wb["एंट्रियाँ"]) if r[1] == "सुरेश"][0]
    assert loader_entry[8] == "लोडिंग 0.5; अनलोडिंग 0.25"


def test_production_excel_by_month(api):
    _seed(api)
    wb = _xlsx(
        api,
        "/api/exports/production.xlsx",
        start="2026-01-01",
        end="2026-12-31",
        group_by="month",
        lang="hi",
    )
    rows = _rows(wb.active)
    assert [r[0] for r in rows[4:]] == ["जनवरी 2026", "फ़रवरी 2026", "कुल"]
    assert Decimal(str(rows[-1][5])) == Decimal("397.5")


def test_export_rejects_bad_period(api):
    resp = api.c.get("/api/exports/wages.xlsx", params={"start": "2026-02-01", "end": "2026-01-01"})
    assert resp.status_code == 422
    assert resp.json()["error"]["details"]["reason"] == "bad_period"


def test_errors_carry_reason_codes(api):
    w = api.worker("Amit")
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    body = {
        "worker_id": w["id"],
        "entry_date": tomorrow,
        "length_ft": "1",
        "width_ft": "1",
        "cuts": 1,
        "quantity": 1,
    }
    future = api.c.post("/api/production", json=body)
    assert future.json()["error"]["details"]["reason"] == "future_date"

    api.ok(api.c.post(f"/api/workers/{w['id']}/archive"))
    archived = api.c.post("/api/production", json={**body, "entry_date": "2026-01-01"})
    assert archived.json()["error"]["details"]["reason"] == "worker_archived"

    wrong = api.c.post(
        "/api/rates",
        json={
            "worker_type_id": api.type_id["machine_operator"],
            "component": "loading",
            "rate_per_sqft": "1",
            "effective_from": "2026-01-01",
        },
    )
    assert wrong.json()["error"]["details"]["reason"] == "component_not_allowed"


def test_missing_files_are_404_not_the_app(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html>app</html>")
    app = create_app(Settings(data_dir=tmp_path / "data", static_dir=static))
    with TestClient(app) as c:
        assert c.get("/favicon.ico").status_code == 404
        assert c.get("/assets/old-build-123.js").status_code == 404
        assert c.get("/reports").text == "<html>app</html>"  # screens still work


def test_command_line_options(tmp_path):
    import pytest

    from fms.__main__ import parse_settings

    s = parse_settings(["--port", "9000", "--data-dir", str(tmp_path)])
    assert s.port == 9000 and s.data_dir == tmp_path and s.host == "127.0.0.1"
    with pytest.raises(SystemExit):
        parse_settings(["--prot", "9000"])  # a typo must fail loudly, not be ignored
