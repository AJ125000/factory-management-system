from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from fms.config import Settings
from fms.main import create_app

OWNER_PASSWORD = "owner-pass-123"


@pytest.fixture
def anonymous(tmp_path) -> Iterator[TestClient]:
    """A fresh app with its own empty database, not logged in."""
    app = create_app(Settings(data_dir=tmp_path, auto_backups=False))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client(anonymous) -> TestClient:
    """A fresh app where the owner has set up the password and this device is logged in."""
    resp = anonymous.post(
        "/api/auth/setup", json={"password": OWNER_PASSWORD, "device_name": "Test laptop"}
    )
    assert resp.status_code == 201, resp.text
    anonymous.headers["Authorization"] = f"Bearer {resp.json()['token']}"
    return anonymous


class Api:
    """Small helpers so tests read like the owner's actions."""

    def __init__(self, client: TestClient) -> None:
        self.c = client
        types = client.get("/api/worker-types").json()
        self.type_id = {t["code"]: t["id"] for t in types}

    def ok(self, resp, status: int = 200) -> Any:
        assert resp.status_code == status, resp.text
        return resp.json() if resp.content else None

    def worker(self, name: str, type_code: str = "machine_operator", **extra) -> dict:
        body = {"name_en": name, "worker_type_id": self.type_id[type_code], **extra}
        return self.ok(self.c.post("/api/workers", json=body), 201)

    def rate(self, type_code: str, component: str, value: str, effective_from: str) -> dict:
        body = {
            "worker_type_id": self.type_id[type_code],
            "component": component,
            "rate_per_sqft": value,
            "effective_from": effective_from,
        }
        return self.ok(self.c.post("/api/rates", json=body), 201)

    def entry(self, worker: dict, entry_date: str, length="2", width="3", cuts=2, quantity=5):
        body = {
            "worker_id": worker["id"],
            "entry_date": entry_date,
            "length_ft": length,
            "width_ft": width,
            "cuts": cuts,
            "quantity": quantity,
        }
        return self.ok(self.c.post("/api/production", json=body), 201)

    def wages(self, start: str, end: str, **params) -> dict:
        return self.ok(
            self.c.get("/api/reports/wages", params={"start": start, "end": end, **params})
        )


@pytest.fixture
def api(client) -> Api:
    return Api(client)
