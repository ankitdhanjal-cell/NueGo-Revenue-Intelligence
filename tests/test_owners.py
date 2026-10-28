import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import main

ADMIN = {"X-User-Id": "admin"}
ANALYST = {"X-User-Id": "analyst-1"}
ROUTES = [dict(id="R1", label="A → B", capacity=40), dict(id="R2", label="A → C", capacity=40)]
WARNINGS = [dict(id="w-S1", service_id="S1", corridor_id="R1"), dict(id="w-S2", service_id="S2", corridor_id="R2")]


@pytest.fixture()
def client(monkeypatch):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(main, "engine", eng)
    monkeypatch.setattr(main.desk_calc, "routes", lambda e: ROUTES)
    monkeypatch.setattr(main.desk_calc, "warnings",
                        lambda e, now=None, route_ids=None: [w for w in WARNINGS if route_ids is None or w["corridor_id"] in route_ids])
    return TestClient(main.app)


def test_starts_empty_and_lists_every_corridor(client):
    items = client.get("/owners", headers=ANALYST).json()["items"]
    assert [i["route_id"] for i in items] == ["R1", "R2"] and all(i["owner_id"] is None for i in items)
    assert client.get("/owners").status_code == 401


def test_only_an_admin_can_assign(client):
    assert client.put("/owners/R1", json={"user_id": "analyst-1"}).status_code == 401
    assert client.put("/owners/R1", json={"user_id": "analyst-1"}, headers=ANALYST).status_code == 403
    r = client.put("/owners/R1", json={"user_id": "analyst-1"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["owner_id"] == "analyst-1" and r.json()["assigned_by"] == "admin"


def test_unknown_corridor_and_user_and_clearing(client):
    assert client.put("/owners/NOPE", json={"user_id": "analyst-1"}, headers=ADMIN).status_code == 404
    assert client.put("/owners/R1", json={"user_id": "ghost"}, headers=ADMIN).status_code == 422
    client.put("/owners/R1", json={"user_id": "analyst-1"}, headers=ADMIN)
    client.put("/owners/R1", json={"user_id": "analyst-2"}, headers=ADMIN)  # reassign replaces
    assert client.get("/owners", headers=ADMIN).json()["items"][0]["owner_id"] == "analyst-2"
    assert client.put("/owners/R1", json={"user_id": None}, headers=ADMIN).json()["owner_id"] is None


def test_warnings_are_filtered_by_owner(client):
    client.put("/owners/R1", json={"user_id": "analyst-1"}, headers=ADMIN)
    everyone = client.get("/warnings").json()["items"]
    assert [w["service_id"] for w in everyone] == ["S1", "S2"]
    assert [w["owner_id"] for w in everyone] == ["analyst-1", None]
    mine = client.get("/warnings", params={"owner_id": "analyst-1"}).json()["items"]
    assert [w["service_id"] for w in mine] == ["S1"]
    assert client.get("/warnings", params={"owner_id": "analyst-2"}).json()["items"] == []  # owns nothing
    assert client.get("/warnings", params={"owner_id": "ghost"}).status_code == 404
