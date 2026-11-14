import json

from sqlalchemy import select

from fms.models import AuditLog, Tombstone


def test_seeded_worker_types(api):
    types = api.ok(api.c.get("/api/worker-types"))
    by_code = {t["code"]: t for t in types}
    assert by_code["machine_operator"]["pay_scheme"] == "cutting"
    assert by_code["machine_operator"]["name_hi"] == "मशीन ऑपरेटर"
    assert by_code["loader"]["pay_scheme"] == "loading"


def test_create_worker_with_hindi_name(api):
    w = api.worker("Ramesh", name_hi="रमेश", phone="98290 12345")
    assert w["name_hi"] == "रमेश"
    assert w["worker_type"]["code"] == "machine_operator"
    assert w["is_archived"] is False


def test_duplicate_name_needs_confirmation(api):
    api.worker("Ramesh")
    resp = api.c.post(
        "/api/workers", json={"name_en": "ramesh ", "worker_type_id": api.type_id["loader"]}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["details"]["reason"] == "duplicate_name"
    # The owner confirms it really is a second person with the same name.
    api.worker("Ramesh", allow_duplicate_name=True)
    assert len(api.ok(api.c.get("/api/workers"))) == 2


def test_validation_errors(api):
    bad = api.c.post("/api/workers", json={"name_en": "", "worker_type_id": api.type_id["loader"]})
    assert bad.status_code == 422
    unknown = api.c.post("/api/workers", json={"name_en": "X", "worker_type_id": "nope"})
    assert unknown.status_code == 422


def test_archive_and_restore(api):
    w = api.worker("Suresh")
    api.ok(api.c.post(f"/api/workers/{w['id']}/archive"))
    assert api.ok(api.c.get("/api/workers")) == []
    archived = api.ok(api.c.get("/api/workers", params={"include_archived": True}))
    assert archived[0]["is_archived"] is True

    # No new production for archived workers.
    resp = api.c.post(
        "/api/production",
        json={
            "worker_id": w["id"],
            "entry_date": "2026-01-05",
            "length_ft": "1",
            "width_ft": "1",
            "cuts": 1,
            "quantity": 1,
        },
    )
    assert resp.status_code == 409

    api.ok(api.c.post(f"/api/workers/{w['id']}/restore"))
    assert len(api.ok(api.c.get("/api/workers"))) == 1


def test_delete_requires_matching_confirmation(api, client):
    w = api.worker("Mahesh")
    api.rate("machine_operator", "cutting", "1.5", "2026-01-01")
    e1 = api.entry(w, "2026-01-05")
    api.entry(w, "2026-01-06")

    impact = api.ok(api.c.get(f"/api/workers/{w['id']}/delete-impact"))
    assert impact["production_entries"] == 2

    stale = api.c.delete(f"/api/workers/{w['id']}", params={"confirm_entries": 1})
    assert stale.status_code == 409
    assert stale.json()["error"]["details"]["production_entries"] == 2

    api.ok(api.c.delete(f"/api/workers/{w['id']}", params={"confirm_entries": 2}), 204)
    assert api.c.get(f"/api/workers/{w['id']}").status_code == 404
    assert api.c.get(f"/api/production/{e1['id']}").status_code == 404

    # Deletion is recorded for sync, and the full data is kept for recovery.
    with client.app.state.session_factory() as s:
        tombs = {(t.entity, t.entity_id) for t in s.scalars(select(Tombstone))}
        assert ("worker", w["id"]) in tombs and ("production_entry", e1["id"]) in tombs
        log = s.scalar(select(AuditLog).where(AuditLog.action == "delete"))
        saved = json.loads(log.before)
        assert saved["worker"]["name_en"] == "Mahesh"
        assert len(saved["production_entries"]) == 2


def test_edits_are_audited(api, client):
    w = api.worker("Ganesh")
    api.ok(api.c.patch(f"/api/workers/{w['id']}", json={"phone": "9876543210"}))
    with client.app.state.session_factory() as s:
        worker_changes = select(AuditLog).where(AuditLog.entity == "worker").order_by(AuditLog.id)
        actions = [a.action for a in s.scalars(worker_changes)]
    assert actions == ["create", "update"]
