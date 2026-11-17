from io import BytesIO

from openpyxl import load_workbook


def test_excel_export_never_turns_typed_text_into_formulas(api):
    w = api.worker('=HYPERLINK("http://evil","pay")')
    api.rate("machine_operator", "cutting", "1.5", "2026-01-01")
    api.entry(w, "2026-01-05")
    resp = api.c.get("/api/exports/wages.xlsx", params={"start": "2026-01-01", "end": "2026-01-31"})
    wb = load_workbook(BytesIO(resp.content))
    cells = [c for ws in wb.worksheets for row in ws.iter_rows() for c in row]
    assert not [c.coordinate for c in cells if c.data_type == "f"]
    assert any(c.value == '=HYPERLINK("http://evil","pay")' for c in cells)  # kept as text


def test_backup_copy_folder_must_be_a_full_path(api, tmp_path):
    relative = api.c.patch("/api/settings", json={"backup_copy_dir": "."})
    assert relative.json()["error"]["details"]["reason"] == "backup_dir_missing"
    assert api.c.patch("/api/settings", json={"backup_copy_dir": str(tmp_path)}).status_code == 200


def test_a_deleted_entry_is_not_brought_back_by_a_late_retry(api):
    import uuid

    w = api.worker("Amit")
    api.rate("machine_operator", "cutting", "1.5", "2026-01-01")
    entry_id = str(uuid.uuid4())
    body = {
        "id": entry_id,
        "worker_id": w["id"],
        "entry_date": "2026-01-05",
        "length_ft": "2",
        "width_ft": "3",
        "cuts": 2,
        "quantity": 5,
    }
    api.ok(api.c.post("/api/production", json=body), 201)
    api.ok(api.c.delete(f"/api/production/{entry_id}"), 204)  # e.g. deleted on the laptop

    late = api.c.post("/api/production", json=body)  # the phone retries its old create
    assert late.status_code == 410
    assert late.json()["error"]["details"]["reason"] == "deleted"
    assert api.ok(api.c.get("/api/production"))["total"] == 0

    # Same for workers.
    wid = str(uuid.uuid4())
    wbody = {"id": wid, "name_en": "Temp", "worker_type_id": api.type_id["loader"]}
    api.ok(api.c.post("/api/workers", json=wbody), 201)
    api.ok(api.c.delete(f"/api/workers/{wid}", params={"confirm_entries": 0}), 204)
    assert api.c.post("/api/workers", json=wbody).status_code == 410


def test_backup_from_a_newer_version_is_refused_cleanly(api, client, tmp_path):
    import sqlite3

    made = api.ok(api.c.post("/api/backups"), 201)
    newer = tmp_path / "newer.db"
    newer.write_bytes(api.c.get(f"/api/backups/{made['name']}/download").content)
    conn = sqlite3.connect(newer)
    conn.execute("UPDATE alembic_version SET version_num = '9999'")
    conn.commit()
    conn.close()

    data_dir = client.app.state.settings.data_dir
    before = {p.name for p in data_dir.iterdir()}
    resp = api.c.post(
        "/api/backups/restore-upload",
        content=newer.read_bytes(),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["details"]["reason"] == "backup_too_new"
    after = {p.name for p in data_dir.iterdir()}
    assert after <= before | {"fms.db-wal", "fms.db-shm"}  # no leftover files
    assert api.c.get("/api/workers").status_code == 200  # data untouched, still logged in


def test_parallel_password_guesses_cannot_beat_the_limit(client):
    from concurrent.futures import ThreadPoolExecutor

    def guess(i):
        return client.post(
            "/api/auth/login",
            json={"password": f"guess-{i}", "device_name": "p"},
            headers={"Authorization": ""},
        ).status_code

    with ThreadPoolExecutor(20) as pool:
        codes = list(pool.map(guess, range(20)))
    assert codes.count(401) == 5  # only the free tries are actually checked
    assert codes.count(429) == 15


def test_requests_for_other_host_names_are_refused(anonymous):
    # DNS rebinding: a web page makes the browser call the hub under its own name.
    evil = anonymous.post(
        "/api/auth/setup",
        json={"password": "attacker-1", "device_name": "x"},
        headers={"Host": "evil.example.com"},
    )
    assert evil.status_code == 400
    assert anonymous.get("/api/auth/status").json()["setup_required"] is True

    for ok_host in ("127.0.0.1:8765", "localhost", "owner-laptop.tail1234.ts.net", "[::1]:8765"):
        assert anonymous.get("/api/health", headers={"Host": ok_host}).status_code == 200


def test_extra_allowed_hosts(anonymous, monkeypatch):
    monkeypatch.setenv("FMS_ALLOWED_HOSTS", "fms.factory.local")
    assert anonymous.get("/api/health", headers={"Host": "fms.factory.local"}).status_code == 200
