import pytest
from conftest import OWNER_PASSWORD
from fastapi.testclient import TestClient
from sqlalchemy import select

from fms.models import DeviceSession, OwnerAccount
from fms.services import auth


def test_first_run_setup_then_everything_needs_login(anonymous):
    status = anonymous.get("/api/auth/status").json()
    assert status == {"setup_required": True, "logged_in": False, "device": None}
    # Data is locked even before the password is set.
    assert anonymous.get("/api/workers").status_code == 401
    assert anonymous.get("/api/health").status_code == 200  # public

    short = anonymous.post("/api/auth/setup", json={"password": "123", "device_name": "Laptop"})
    assert short.json()["error"]["details"]["reason"] == "password_too_short"

    ok = anonymous.post(
        "/api/auth/setup", json={"password": OWNER_PASSWORD, "device_name": "Laptop"}
    )
    assert ok.status_code == 201
    token = ok.json()["token"]

    again = anonymous.post("/api/auth/setup", json={"password": "another-one", "device_name": "X"})
    assert again.status_code == 409  # can't be used to take over once set up

    headers = {"Authorization": f"Bearer {token}"}
    assert anonymous.get("/api/workers", headers=headers).status_code == 200
    me = anonymous.get("/api/auth/status", headers=headers).json()
    assert me["logged_in"] and me["device"]["name"] == "Laptop" and me["device"]["current"]


def test_login_wrong_password_and_throttling(client):
    anon = {"Authorization": ""}
    bad = client.post(
        "/api/auth/login", json={"password": "nope", "device_name": "Phone"}, headers=anon
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["details"]["reason"] == "wrong_password"

    for _ in range(4):
        client.post("/api/auth/login", json={"password": "nope", "device_name": "P"}, headers=anon)
    slowed = client.post(
        "/api/auth/login", json={"password": OWNER_PASSWORD, "device_name": "P"}, headers=anon
    )
    assert slowed.status_code == 429  # even the right password must wait now
    assert slowed.json()["error"]["details"]["retry_after_seconds"] > 0


def test_devices_can_be_signed_out(client):
    phone = client.post(
        "/api/auth/login",
        json={"password": OWNER_PASSWORD, "device_name": "Owner's phone"},
        headers={"Authorization": ""},
    ).json()
    phone_headers = {"Authorization": f"Bearer {phone['token']}"}
    assert client.get("/api/workers", headers=phone_headers).status_code == 200

    devices = client.get("/api/auth/devices").json()
    assert {d["name"] for d in devices} == {"Test laptop", "Owner's phone"}
    assert [d["current"] for d in devices if d["name"] == "Test laptop"] == [True]

    # The phone is lost: sign it out from the laptop.
    assert client.delete(f"/api/auth/devices/{phone['device']['id']}").status_code == 204
    assert client.get("/api/workers", headers=phone_headers).status_code == 401
    assert client.get("/api/workers").status_code == 200  # the laptop is unaffected


def test_logout(client):
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/workers").status_code == 401


def test_change_password(client):
    other = client.post(
        "/api/auth/login",
        json={"password": OWNER_PASSWORD, "device_name": "PC"},
        headers={"Authorization": ""},
    ).json()
    wrong = client.post(
        "/api/auth/password",
        json={"current_password": "nope", "new_password": "new-password-1"},
    )
    assert wrong.status_code == 401
    ok = client.post(
        "/api/auth/password",
        json={
            "current_password": OWNER_PASSWORD,
            "new_password": "new-password-1",
            "sign_out_other_devices": True,
        },
    )
    assert ok.json() == {"signed_out_devices": 1}
    assert client.get("/api/workers").status_code == 200
    assert (
        client.get(
            "/api/workers", headers={"Authorization": f"Bearer {other['token']}"}
        ).status_code
        == 401
    )
    relogin = client.post(
        "/api/auth/login",
        json={"password": "new-password-1", "device_name": "PC"},
        headers={"Authorization": ""},
    )
    assert relogin.status_code == 200


def test_secrets_are_never_stored_in_plain_text(client):
    with client.app.state.session_factory() as s:
        owner = s.get(OwnerAccount, 1)
        assert OWNER_PASSWORD not in owner.password_hash
        assert owner.password_hash.startswith("scrypt$")
        token = client.headers["Authorization"].split()[1]
        assert all(token not in d.token_hash for d in s.scalars(select(DeviceSession)))


def test_reset_password_signs_everyone_out(client):
    with client.app.state.session_factory() as s:
        assert auth.reset_password(s, "reset-pass-9") == 1
        s.commit()
    assert client.get("/api/workers").status_code == 401
    with pytest.raises(auth.Invalid), client.app.state.session_factory() as s:
        auth.reset_password(s, "123")


def test_password_hashing_round_trip():
    stored = auth.hash_password("secret-1")
    assert auth.verify_password("secret-1", stored)
    assert not auth.verify_password("secret-2", stored)
    assert not auth.verify_password("secret-1", "garbage")
    assert auth.hash_password("secret-1") != stored  # salted


def test_reset_password_command(tmp_path):
    from fms.__main__ import reset_password
    from fms.config import Settings
    from fms.main import create_app

    output: list[str] = []
    answers = iter(["laptop-reset-1", "different"])
    assert (
        reset_password(
            ["--data-dir", str(tmp_path)], ask=lambda _: next(answers), out=output.append
        )
        == 1
    )
    assert "don't match" in output[-1]

    answers = iter(["laptop-reset-1", "laptop-reset-1"])
    assert (
        reset_password(
            ["--data-dir", str(tmp_path)], ask=lambda _: next(answers), out=output.append
        )
        == 0
    )

    with TestClient(create_app(Settings(data_dir=tmp_path))) as c:
        login = c.post(
            "/api/auth/login", json={"password": "laptop-reset-1", "device_name": "Laptop"}
        )
        assert login.status_code == 200
