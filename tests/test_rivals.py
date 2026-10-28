import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import main, rivals

OURS = pd.Series(dict(service_id="S1", route_id="R1", departure_at=pd.Timestamp("2026-05-10 08:00"),
                      fare_on_sale=500.0, avg_rating=4.2, num_ratings=900,
                      booking_time=pd.Timestamp("2026-05-05 12:00")))
AS_OF = pd.Timestamp("2026-05-05 12:00")


def _comp(*rows):
    cols = ["operator", "route_id", "departure_at", "fare", "captured_at"]
    df = pd.DataFrame(rows, columns=cols)
    df["departure_at"] = pd.to_datetime(df["departure_at"])
    df["captured_at"] = pd.to_datetime(df["captured_at"])
    return df


def test_names_never_appear_and_labels_follow_departure_order():
    comp = _comp(("SecretBus", "R1", "2026-05-10 08:20", 450, "2026-05-04 09:00"),
                 ("OtherCo", "R1", "2026-05-10 07:45", 520, "2026-05-04 09:00"))
    out = rivals.rival_view(OURS, comp, AS_OF)
    text = json.dumps(out)
    assert "SecretBus" not in text and "OtherCo" not in text
    assert [r["label"] for r in out["rivals"]] == ["Rival A", "Rival B"]
    assert [r["minutes_from_ours"] for r in out["rivals"]] == [-15, 20]


def test_gap_is_our_fare_minus_rival_fare():
    out = rivals.rival_view(OURS, _comp(("A", "R1", "2026-05-10 08:00", 450, "2026-05-04 09:00")), AS_OF)
    assert out["rivals"][0]["gap_to_ours"] == 50.0 and out["flags"]["rival_missing"] is False


@pytest.mark.parametrize("dep,kept", [("2026-05-10 08:30", True), ("2026-05-10 07:30", True),
                                      ("2026-05-10 08:31", False), ("2026-05-10 07:29", False)])
def test_window_is_plus_minus_30_minutes_inclusive(dep, kept):
    out = rivals.rival_view(OURS, _comp(("A", "R1", dep, 450, "2026-05-04 09:00")), AS_OF)
    assert (out["rival_count"] == 1) is kept


def test_captures_after_as_of_are_ignored():
    comp = _comp(("A", "R1", "2026-05-10 08:00", 450, "2026-05-05 12:01"))
    out = rivals.rival_view(OURS, comp, AS_OF)
    assert out["rivals"] == [] and out["flags"]["rival_missing"] is True


def test_latest_capture_at_or_before_as_of_wins():
    comp = _comp(("A", "R1", "2026-05-10 08:00", 400, "2026-05-01 09:00"),
                 ("A", "R1", "2026-05-10 08:00", 430, "2026-05-05 12:00"),
                 ("A", "R1", "2026-05-10 08:00", 999, "2026-05-06 09:00"))
    out = rivals.rival_view(OURS, comp, AS_OF)
    assert out["rival_count"] == 1 and out["rivals"][0]["fare"] == 430


def test_other_route_is_ignored_and_missing_rating_is_none():
    ours = OURS.copy()
    ours["avg_rating"] = float("nan")
    out = rivals.rival_view(ours, _comp(("A", "R2", "2026-05-10 08:00", 450, "2026-05-04 09:00")), AS_OF)
    assert out["rival_count"] == 0 and out["route_rating"] == {"avg": None, "count": 900}


def test_label_runs_past_z():
    assert rivals.rival_label(0) == "Rival A" and rivals.rival_label(25) == "Rival Z"
    assert rivals.rival_label(26) == "Rival AA"


@pytest.fixture()
def client(monkeypatch):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    svc = pd.DataFrame([OURS.to_dict()])
    svc.to_sql("services", eng, index=False)
    _comp(("SecretBus", "R1", "2026-05-10 08:10", 450, "2026-05-04 09:00"),
          ("Late", "R1", "2026-05-10 08:00", 300, "2026-05-09 09:00")).to_sql("competitor_fares", eng, index=False)
    monkeypatch.setattr(main, "engine", eng)
    return TestClient(main.app)


def test_api_returns_rival_and_hides_name(client):
    r = client.get("/rivals/services/S1")
    assert r.status_code == 200 and "SecretBus" not in r.text
    assert r.json()["rival_count"] == 1 and r.json()["route_rating"] == {"avg": 4.2, "count": 900}


def test_api_as_of_later_shows_later_capture(client):
    r = client.get("/rivals/services/S1", params={"as_of": "2026-05-09T10:00"})
    assert r.json()["rival_count"] == 2


def test_api_404_and_422(client):
    assert client.get("/rivals/services/NOPE").status_code == 404
    assert client.get("/rivals/services/S1", params={"as_of": "not-a-date"}).status_code == 422
