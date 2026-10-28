import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import elasticity, main


def _seg(n, slope=None, fares=None, seed=0):
    rng = np.random.default_rng(seed)
    fare = np.asarray(fares) if fares is not None else rng.integers(300, 700, n).astype(float)
    seats = 30 * (fare / 500) ** (slope if slope is not None else 0) * np.exp(rng.normal(0, 0.05, n))
    return pd.DataFrame(dict(fare_on_sale=fare, seats_sold=seats, total_seats=100, flag_cancelled=False))


def test_few_services_gives_no_slope():
    r = elasticity.elasticity(_seg(10, slope=-1))
    assert r["elasticity"] is None and r["enough_data"] is False and "not_enough_services" in r["reason"]


def test_too_few_distinct_fares_gives_no_slope():
    r = elasticity.elasticity(_seg(40, slope=-1, fares=[400.0, 500.0] * 20))
    assert r["elasticity"] is None and "not_enough_fare_variation" in r["reason"]


def test_negative_slope_is_recovered_with_ordered_range():
    r = elasticity.elasticity(_seg(120, slope=-1.2))
    e = r["elasticity"]
    assert r["enough_data"] is True and e["low"] <= e["mid"] <= e["high"] and e["mid"] == pytest.approx(-1.2, abs=0.1)


def test_positive_slope_is_not_a_price_response():
    r = elasticity.elasticity(_seg(120, slope=0.8))
    assert r["enough_data"] is False and r["reason"].startswith("fare_follows_demand") and r["elasticity"]["mid"] > 0


def test_same_data_same_range():
    a = elasticity.elasticity(_seg(80, slope=-1))
    assert a == elasticity.elasticity(_seg(80, slope=-1))


def test_cancelled_and_zero_seat_rows_are_left_out():
    s = _seg(60, slope=-1)
    s.loc[:9, "flag_cancelled"] = True
    s.loc[10:14, "seats_sold"] = 0
    assert elasticity.elasticity(s)["n_services"] == 45


def test_sold_out_services_are_left_out_and_counted():
    s = _seg(60, slope=-1)
    s.loc[:4, "seats_sold"] = 100
    r = elasticity.elasticity(s)
    assert r["n_services"] == 55 and r["sold_out_left_out"] == 5


def test_segment_columns():
    assert [elasticity.slot_of(h) for h in (6, 13, 17, 22)] == ["morning", "afternoon", "evening", "night"]
    assert elasticity.day_type_of(5, 0.0) == "weekend" and elasticity.day_type_of(1, 0.5) == "holiday"
    s = pd.DataFrame(dict(departure_at=pd.to_datetime(["2026-05-09 06:00"]), days_to_go=[5.0], holiday_score=[0.0]))
    row = elasticity.add_segment_columns(s).iloc[0]
    assert (row["slot"], row["dtg_band"], row["day_type"]) == ("morning", "3-7", "weekend")


@pytest.fixture()
def client(monkeypatch):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    d = _seg(60, slope=-1)
    d["route_id"], d["departure_at"] = "R1", pd.Timestamp("2026-05-04 07:00")  # Monday morning
    d["days_to_go"], d["holiday_score"] = 5.0, 0.0
    d.to_sql("services", eng, index=False)
    monkeypatch.setattr(main, "engine", eng)
    return TestClient(main.app)


def test_api_shape_and_segment_filter(client):
    r = client.get("/pricing/elasticity", params={"route_id": "R1"}).json()
    assert r["enough_data"] is True and r["flags"]["insufficient_data"] is False and r["n_services"] == 60
    r = client.get("/pricing/elasticity", params={"route_id": "R1", "slot": "night"}).json()
    assert r["n_services"] == 0 and r["elasticity"] is None and r["flags"]["insufficient_data"] is True


def test_api_404_and_422(client):
    assert client.get("/pricing/elasticity", params={"route_id": "NOPE"}).status_code == 404
    assert client.get("/pricing/elasticity", params={"route_id": "R1", "slot": "noon"}).status_code == 422
    assert client.get("/pricing/elasticity").status_code == 422
