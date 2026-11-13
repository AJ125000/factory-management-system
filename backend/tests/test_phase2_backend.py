from fastapi.testclient import TestClient

from fms.config import Settings
from fms.main import create_app


def test_settings_defaults_and_update(api):
    s = api.ok(api.c.get("/api/settings"))
    assert s["print_language"] == "hi"
    assert s["ui_language"] == "en"
    updated = api.ok(
        api.c.patch(
            "/api/settings",
            json={"factory_name_en": "Shree Ganesh Stone", "factory_name_hi": "श्री गणेश स्टोन"},
        )
    )
    assert updated["factory_name_hi"] == "श्री गणेश स्टोन"
    assert api.ok(api.c.get("/api/settings"))["factory_name_en"] == "Shree Ganesh Stone"
    bad = api.c.patch("/api/settings", json={"ui_language": "fr"})
    assert bad.status_code == 422


def test_wage_preview_does_not_save(api):
    w = api.worker("Amit")
    api.rate("machine_operator", "cutting", "1.5", "2026-01-01")
    body = {
        "worker_id": w["id"],
        "entry_date": "2026-01-05",
        "length_ft": "2",
        "width_ft": "3",
        "cuts": 2,
        "quantity": 5,
    }
    preview = api.ok(api.c.post("/api/production/preview", json=body))
    assert preview["wage"] == "180.00"
    assert preview["area_sqft"] == "30"
    assert api.ok(api.c.get("/api/production"))["total"] == 0

    early = api.ok(api.c.post("/api/production/preview", json={**body, "entry_date": "2025-12-01"}))
    assert early["wage"] is None and early["missing_rates"] == ["cutting"]


def test_serves_frontend_with_spa_fallback(tmp_path):
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>app</html>")
    (static / "assets" / "app-123.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("nope")

    app = create_app(Settings(data_dir=tmp_path / "data", static_dir=static))
    with TestClient(app) as c:
        assert c.get("/").text == "<html>app</html>"
        assert c.get("/workers/123").text == "<html>app</html>"  # screen inside the app
        asset = c.get("/assets/app-123.js")
        assert asset.text == "console.log(1)"
        assert "immutable" in asset.headers["cache-control"]
        (static / "sw.js").write_text("// sw")
        assert c.get("/sw.js").headers["cache-control"] == "no-cache"  # updates reach phones
        assert c.get("/api/does-not-exist").status_code == 404
        assert c.get("/api/health").json()["status"] == "ok"
        # Path traversal must never escape the static folder.
        assert "nope" not in c.get("/..%2Fsecret.txt").text
