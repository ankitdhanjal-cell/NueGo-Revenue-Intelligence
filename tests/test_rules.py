import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import main, rules
from app.config import DEFAULT_RULES


@pytest.fixture()
def client(monkeypatch):
    """The API on a throwaway in-memory database, so the shared Postgres is never touched."""
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(main, "engine", eng)
    return TestClient(main.app, headers={"X-User-Id": "admin"})


def _body(**changes):
    return {**DEFAULT_RULES, **changes}


def test_get_returns_default_row_with_fare_steps(client):
    r = client.get("/rules").json()
    assert r["version"] == 1 and r["ceiling"] == DEFAULT_RULES["ceiling"]
    assert r["fare_steps"][0] == 200 and r["fare_steps"][-1] == 1500 and r["updated_by"].startswith("default")


def test_put_adds_a_new_version_and_keeps_the_old_one(client):
    client.get("/rules")
    new = client.put("/rules", json=_body(ceiling=900, updated_by="ops")).json()
    assert new["version"] == 2 and new["updated_by"] == "ops"
    assert client.get("/rules").json()["ceiling"] == 900  # read from the DB each time, no restart
    with main.engine.connect() as con:
        assert len(con.execute(rules.pricing_rules.select()).fetchall()) == 2


@pytest.mark.parametrize("bad", [
    dict(ceiling=0), dict(ceiling=-5), dict(max_change_pct=0), dict(max_change_pct=101),
    dict(min_minutes_between_changes=-1), dict(seats_weight=-0.1), dict(state_cap=0),
    dict(floor_switch_hours=-1), dict(fare_steps=[]), dict(fare_steps=[0, 10]),
    dict(fare_steps=[300, 200]), dict(fare_steps=[200, 200, 300]),
    dict(ceiling=100, fare_steps=[200, 300]),   # ceiling below the smallest step
    dict(state_cap=100, fare_steps=[200, 300]),
])
def test_put_rejects_invalid_input_with_422(client, bad):
    r = client.put("/rules", json=_body(**bad))
    assert r.status_code == 422
    assert client.get("/rules").json()["version"] == 1  # nothing was saved


def test_missing_field_is_422(client):
    body = _body()
    del body["ceiling"]
    assert client.put("/rules", json=body).status_code == 422


def test_state_cap_can_be_null_or_set(client):
    assert client.put("/rules", json=_body(state_cap=None)).json()["state_cap"] is None
    assert client.put("/rules", json=_body(state_cap=700)).json()["state_cap"] == 700


def test_seed_is_idempotent():
    eng = create_engine("sqlite://")
    rules.ensure_rules(eng)
    rules.ensure_rules(eng)
    assert rules.active_rules(eng)["version"] == 1


def test_model_validates_directly():
    with pytest.raises(ValidationError):
        rules.RulesIn(**_body(fare_steps=[10, 5]))


def test_only_an_admin_can_change_the_rules(client):
    anyone = TestClient(main.app)
    assert anyone.put("/rules", json=_body()).status_code == 401
    assert anyone.put("/rules", json=_body(), headers={"X-User-Id": "analyst-1"}).status_code == 403
    assert client.get("/rules").json()["version"] == 1  # nothing was saved
    assert anyone.get("/rules").status_code == 200  # reading is open
