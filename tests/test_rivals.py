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


def test_operator_names_in_departure_order_and_nuego_is_never_a_rival():
    comp = _comp(("FlixBus", "R1", "2026-05-10 08:20", 450, "2026-05-04 09:00"),
                 ("zingbus", "R1", "2026-05-10 07:45", 520, "2026-05-04 09:00"),
                 ("NueGo", "R1", "2026-05-10 08:00", 300, "2026-05-04 09:00"))
    out = rivals.rival_view(OURS, comp, AS_OF)
    assert [r["operator"] for r in out["rivals"]] == ["zingbus", "FlixBus"]
    assert [r["minutes_from_ours"] for r in out["rivals"]] == [-15, 20]
    assert "NueGo" not in json.dumps(out)


def test_nearby_fares_cover_3_days_and_mark_late_captures():
    comp = _comp(("A", "R1", "2026-05-13 08:00", 450, "2026-05-04 09:00"),
                 ("B", "R1", "2026-05-08 10:00", 480, "2026-05-07 09:00"),
                 ("C", "R1", "2026-05-13 08:01", 500, "2026-05-04 09:00"),
                 ("D", "R2", "2026-05-10 08:00", 400, "2026-05-04 09:00"))
    out = rivals.rival_view(OURS, comp, AS_OF)
    assert out["rivals"] == [] and out["nearby_days"] == 3
    assert [(f["operator"], f["gap_to_ours"], f["captured_after_prediction_time"]) for f in out["nearby_fares"]] == \
        [("B", 20.0, True), ("A", 50.0, False)]


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


def test_missing_reason_says_why_no_rival_is_shown():
    assert rivals.rival_view(OURS, _comp(("A", "R1", "2026-05-10 08:00", 450, "2026-05-04 09:00")),
                             AS_OF)["missing_reason"] is None
    later = rivals.rival_view(OURS, _comp(("A", "R1", "2026-05-10 08:00", 450, "2026-05-06 09:00")), AS_OF)
    assert later["missing_reason"] == "captured_after_prediction_time"
    assert later["note"].startswith("1 rival departure(s) within 30 minutes") and "05 May 2026 12:00" in later["note"]
    far = rivals.rival_view(OURS, _comp(("A", "R1", "2026-05-11 11:05", 450, "2026-05-04 09:00")), AS_OF)
    assert far["missing_reason"] == "none_within_30_minutes" and "1 d 3 h 5 min away" in far["note"]
    none = rivals.rival_view(OURS, _comp(("A", "R2", "2026-05-10 08:00", 450, "2026-05-04 09:00")), AS_OF)
    assert none["missing_reason"] == "no_route_data"


@pytest.fixture()
def client(monkeypatch):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    svc = pd.DataFrame([OURS.to_dict()])
    svc.to_sql("services", eng, index=False)
    _comp(("SecretBus", "R1", "2026-05-10 08:10", 450, "2026-05-04 09:00"),
          ("Late", "R1", "2026-05-10 08:00", 300, "2026-05-09 09:00")).to_sql("competitor_fares", eng, index=False)
    monkeypatch.setattr(main, "engine", eng)
    return TestClient(main.app)


def test_api_returns_rival_with_its_name(client):
    r = client.get("/rivals/services/S1")
    assert r.status_code == 200 and r.json()["rivals"][0]["operator"] == "SecretBus"
    assert r.json()["rival_count"] == 1 and r.json()["route_rating"] == {"avg": 4.2, "count": 900}


def test_api_as_of_later_shows_later_capture(client):
    r = client.get("/rivals/services/S1", params={"as_of": "2026-05-09T10:00"})
    assert r.json()["rival_count"] == 2


def test_api_404_and_422(client):
    assert client.get("/rivals/services/NOPE").status_code == 404
    assert client.get("/rivals/services/S1", params={"as_of": "not-a-date"}).status_code == 422


def test_either_side_picks_the_nearest_rival_before_and_at_or_after_ours():
    rows = [dict(label=l, minutes_from_ours=m) for l, m in [("A", -25), ("B", -5), ("C", 0), ("D", 20)]]
    sides = rivals.either_side(rows)
    assert sides["before"]["label"] == "B" and sides["after"]["label"] == "C"
    assert rivals.either_side([]) == dict(before=None, after=None)
