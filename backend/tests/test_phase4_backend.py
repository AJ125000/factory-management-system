import json
import uuid
from decimal import Decimal
from pathlib import Path

import pytest

from fms import tailscale
from fms.wages import MissingRateError, Piece, calculate_wage

CASES = json.loads(
    (Path(__file__).parents[2] / "shared" / "wage-cases.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_shared_wage_cases(case):
    """The same cases are checked by the app's tests, so phone and laptop always agree."""
    rft = case["piece_rft"]
    entry = Piece(
        Decimal(case["piece_sqft"]),
        None if rft is None else Decimal(rft),
        case["cuts"],
        case["quantity"],
        case["batti"],
    )
    rates = {k: None if v is None else Decimal(v) for k, v in case["rates"].items()}
    expected = case["expected"]
    if expected["missing"]:
        with pytest.raises(MissingRateError) as exc:
            calculate_wage(case["kind"], case["role"], entry, rates)
        assert [str(c) for c in exc.value.components] == expected["missing"]
    else:
        result = calculate_wage(case["kind"], case["role"], entry, rates)
        assert str(result.total) == expected["total"]
        assert [str(line.amount) for line in result.lines] == [
            line["amount"] for line in expected["lines"]
        ]


def test_device_chosen_ids_and_safe_retries(api):
    worker_id = str(uuid.uuid4())
    body = {"id": worker_id, "name_en": "Ramesh", "worker_type_id": api.type_id["machine_operator"]}
    first = api.ok(api.c.post("/api/workers", json=body), 201)
    assert first["id"] == worker_id
    # The phone didn't hear back and sends the same change again: no duplicate, no error.
    again = api.ok(api.c.post("/api/workers", json=body), 201)
    assert again["id"] == worker_id
    assert len(api.ok(api.c.get("/api/workers"))) == 1

    rate_id = str(uuid.uuid4())
    rate = {
        "id": rate_id,
        "kind": "block_cutting",
        "component": "cutting",
        "rate": "1.5",
        "effective_from": "2026-01-01",
    }
    api.ok(api.c.post("/api/rates", json=rate), 201)
    api.ok(api.c.post("/api/rates", json=rate), 201)  # would be a duplicate-date conflict otherwise
    assert len(api.ok(api.c.get("/api/rates", params={"kind": "block_cutting"}))) == 1

    entry_id = str(uuid.uuid4())
    entry = {
        "id": entry_id,
        "worker_id": worker_id,
        "entry_date": "2026-01-05",
        "length_ft": "2",
        "width_ft": "3",
        "cuts": 2,
        "quantity": 5,
    }
    assert api.ok(api.c.post("/api/production", json=entry), 201)["wage"] == "180.00"
    api.ok(api.c.post("/api/production", json=entry), 201)
    assert api.ok(api.c.get("/api/production"))["total"] == 1

    bad = api.c.post("/api/workers", json={**body, "id": "not-a-uuid"})
    assert bad.status_code == 422


def test_connect_info(api, monkeypatch):
    monkeypatch.setattr(
        tailscale,
        "detect",
        lambda: tailscale.TailscaleInfo(
            installed=True, running=True, dns_name="owner-laptop.tail1234.ts.net"
        ),
    )
    info = api.ok(api.c.get("/api/connect-info"))
    assert info["detected_url"] == "https://owner-laptop.tail1234.ts.net/"
    assert info["phone_url"] == info["detected_url"]

    api.ok(api.c.patch("/api/settings", json={"phone_url": "https://other.example.ts.net/"}))
    assert api.ok(api.c.get("/api/connect-info"))["phone_url"] == "https://other.example.ts.net/"
    assert api.c.patch("/api/settings", json={"phone_url": "not a url"}).status_code == 422


def test_tailscale_detection_without_tailscale():
    info = tailscale.detect(cli="/definitely/not/installed/tailscale")
    assert info.installed is True and info.running is False and info.url is None
