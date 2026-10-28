import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import decisions, main
from app.decisions import DecisionIn

ANALYST = {"X-User-Id": "analyst-1"}


def _inputs():
    svc = dict(service_id="S1", route_id="R1", fare_on_sale=500.0, cost_to_run=15000.0, margin_status="ok",
               flag_cancelled=False, checkpoint_status="ok", hours_to_departure=100.0, marginal_floor=float("nan"),
               average_floor_low=380.0, average_floor_mid=450.0, average_floor_high=600.0, seats_sold=20.0,
               holiday_score=0.0, holiday_event="x", avg_rating=4.0, num_ratings=500, rival_median=None,
               predicted_fare=dict(low=450.0, mid=520.0, high=590.0, label="x"))
    rules = dict(version=1, floor_switch_hours=24.0, ceiling=1500.0, state_cap=None, max_change_pct=15.0,
                 min_minutes_between_changes=240, seats_weight=0.0, fare_steps=[float(x) for x in range(200, 1501, 10)])

    def seat_fn(fares):
        return {f: dict(low=10.0, mid=15.0, high=20.0) for f in fares}
    return dict(svc=svc, rules=rules, seat_fn=seat_fn, band=None, rivals=[])


@pytest.fixture()
def client(monkeypatch):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(main, "engine", eng)
    monkeypatch.setattr(decisions, "load_inputs", lambda engine, sid: _inputs() if sid == "S1" else None)
    return TestClient(main.app)


def test_approve_records_the_suggested_fare_and_nothing_else(client):
    r = client.post("/suggestions/S1/decision", json={"action": "approve"}, headers=ANALYST)
    assert r.status_code == 201
    d = r.json()
    assert d["action"] == "approve" and d["fare"] == d["our_fare"] == 520.0 and d["engine_fare"] == 500.0
    assert d["user"] == "Pricing analyst 1" and d["outcome"] is None
    assert client.get("/decisions", params={"service_id": "S1"}).json()["items"][0]["id"] == d["id"]


def test_change_needs_an_allowed_fare_and_a_reason(client):
    bad = client.post("/suggestions/S1/decision", json={"action": "change", "fare": 900, "reason": "x"}, headers=ANALYST)
    assert bad.status_code == 422 and bad.json()["detail"][0]["loc"] == ["body", "fare"]
    no_reason = client.post("/suggestions/S1/decision", json={"action": "change", "fare": 510}, headers=ANALYST)
    assert no_reason.status_code == 422 and no_reason.json()["detail"][0]["loc"] == ["body", "reason"]
    ok = client.post("/suggestions/S1/decision", json={"action": "change", "fare": 510, "reason": "demand"}, headers=ANALYST)
    assert ok.status_code == 201 and ok.json()["fare"] == 510 and ok.json()["reason"] == "demand"
    assert client.get("/decisions").json()["items"][0]["fare"] == 510


def test_reject_and_wrong_need_their_fields(client):
    assert client.post("/suggestions/S1/decision", json={"action": "reject"}, headers=ANALYST).status_code == 422
    r = client.post("/suggestions/S1/decision", json={"action": "wrong", "reason": "x"}, headers=ANALYST)
    assert r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", "category"]
    ok = client.post("/suggestions/S1/decision", json={"action": "wrong", "reason": "x", "category": "cost_wrong"}, headers=ANALYST)
    assert ok.status_code == 201 and ok.json()["fare"] is None and ok.json()["category"] == "cost_wrong"


def test_a_second_decision_is_a_409_that_says_who_decided(client):
    client.post("/suggestions/S1/decision", json={"action": "approve"}, headers=ANALYST)
    again = client.post("/suggestions/S1/decision", json={"action": "reject", "reason": "x"}, headers={"X-User-Id": "analyst-2"})
    assert again.status_code == 409 and "Already decided by Pricing analyst 1" in again.json()["detail"]


def test_who_you_are_and_unknown_service(client):
    assert client.post("/suggestions/S1/decision", json={"action": "approve"}).status_code == 401
    assert client.post("/suggestions/NOPE/decision", json={"action": "approve"}, headers=ANALYST).status_code == 404
    assert client.post("/suggestions/S1/decision", json={"action": "fly"}, headers=ANALYST).status_code == 422


def test_cannot_approve_when_there_is_no_suggestion(client, monkeypatch):
    inp = _inputs()
    inp["svc"]["average_floor_mid"] = 900.0  # no allowed fare
    monkeypatch.setattr(decisions, "load_inputs", lambda engine, sid: inp)
    r = client.post("/suggestions/S1/decision", json={"action": "approve"}, headers=ANALYST)
    assert r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", "action"]


def test_validate_directly():
    assert decisions.validate(DecisionIn(action="approve"), 500.0, []) == []
    assert decisions.validate(DecisionIn(action="reject", reason="  "), 500.0, [])[0]["loc"] == ["body", "reason"]
    assert decisions.decided_service_ids(create_engine("sqlite://")) == set()
    assert pd.Series([1]).sum() == 1
