import sqlite3
from datetime import datetime, timedelta

from fms.services import backups


def _backups(api):
    return api.ok(api.c.get("/api/backups"))


def test_back_up_now_list_and_download(api, client, tmp_path):
    api.worker("Ramesh")
    made = api.ok(api.c.post("/api/backups"), 201)
    assert made["kind"] == "manual" and made["size"] > 0

    status = _backups(api)
    assert [b["name"] for b in status["backups"]] == [made["name"]]
    assert status["last_backup_at"] is not None
    assert status["copy_dir_ok"] is None  # no extra folder set

    file = api.c.get(f"/api/backups/{made['name']}/download")
    assert file.status_code == 200
    path = tmp_path / "downloaded.db"
    path.write_bytes(file.content)
    names = sqlite3.connect(path).execute("SELECT name_en FROM workers").fetchall()
    assert names == [("Ramesh",)]

    # Only backups the hub made can be downloaded: no reaching other files.
    assert api.c.get("/api/backups/..%2Ffms.db/download").status_code == 404
    assert api.c.get("/api/backups/fms.db/download").status_code == 404


def test_backups_need_login(anonymous):
    assert anonymous.get("/api/backups").status_code == 401
    assert anonymous.post("/api/backups").status_code == 401


def test_restore_brings_data_back_and_keeps_logins(api, client):
    api.worker("Ramesh")
    snapshot = api.ok(api.c.post("/api/backups"), 201)
    api.worker("Suresh")  # added after the backup
    assert len(api.ok(api.c.get("/api/workers"))) == 2

    safety = api.ok(api.c.post(f"/api/backups/{snapshot['name']}/restore"))
    assert safety["kind"] == "before-restore"

    # Data is as it was in the backup, and this device is still logged in.
    assert [w["name_en"] for w in api.ok(api.c.get("/api/workers"))] == ["Ramesh"]

    # The safety copy can undo the restore.
    api.ok(api.c.post(f"/api/backups/{safety['name']}/restore"))
    assert len(api.ok(api.c.get("/api/workers"))) == 2


def test_restore_from_uploaded_file(api, client, tmp_path):
    api.worker("Ramesh")
    made = api.ok(api.c.post("/api/backups"), 201)
    content = api.c.get(f"/api/backups/{made['name']}/download").content
    api.worker("Suresh")

    resp = api.c.post(
        "/api/backups/restore-upload",
        content=content,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 200, resp.text
    assert [w["name_en"] for w in api.ok(api.c.get("/api/workers"))] == ["Ramesh"]


def test_rejects_files_that_are_not_backups(api, client):
    junk = api.c.post(
        "/api/backups/restore-upload",
        content=b"definitely not a database",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert junk.status_code == 422
    assert junk.json()["error"]["details"]["reason"] == "not_a_backup"
    assert api.ok(api.c.get("/api/workers")) == []  # nothing changed


def test_extra_backup_folder(api, client, tmp_path):
    missing = api.c.patch("/api/settings", json={"backup_copy_dir": str(tmp_path / "nope")})
    assert missing.json()["error"]["details"]["reason"] == "backup_dir_missing"

    usb = tmp_path / "usb"
    usb.mkdir()
    api.ok(api.c.patch("/api/settings", json={"backup_copy_dir": str(usb)}))
    made = api.ok(api.c.post("/api/backups"), 201)
    assert (usb / made["name"]).is_file()
    assert _backups(api)["copy_dir_ok"] is True


def test_daily_schedule_and_pruning(client):
    state = client.app.state
    settings = state.settings
    scheduler = state.backup_scheduler
    assert scheduler.tick() is True  # nothing yet: back up now
    assert scheduler.tick() is False  # not due again for a day

    now = datetime.now()
    assert backups.due(settings.data_dir, now + timedelta(hours=23)) is False
    assert backups.due(settings.data_dir, now + timedelta(hours=25)) is True

    for _ in range(backups.KEEP + 3):
        backups.create_backup(settings.db_path, settings.data_dir, "manual")
    assert len(backups.list_backups(settings.data_dir)) == backups.KEEP
