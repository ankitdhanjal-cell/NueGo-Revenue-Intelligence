import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app import fare_model
from app.main import app


def _comp(captured, fare=300.0, dep="2025-01-10 08:00", route="R1"):
    return dict(route_id=route, captured_at=pd.Timestamp(captured), departure_at=pd.Timestamp(dep), fare=fare)


def test_competitor_join_ignores_rows_captured_after_prediction_time():
    comp = pd.DataFrame([_comp("2025-01-08 10:00", 300), _comp("2025-01-09 10:00", 900)])
    f = fare_model.competitor_features("R1", pd.Timestamp("2025-01-10 08:00"), pd.Timestamp("2025-01-08 12:00"), comp)
    assert f["comp_n"] == 1 and f["comp_median_fare"] == 300


def test_competitor_join_respects_route_and_window():
    comp = pd.DataFrame([_comp("2025-01-01", 300, route="R2"), _comp("2025-01-01", 400, dep="2025-01-20 08:00")])
    f = fare_model.competitor_features("R1", pd.Timestamp("2025-01-10 08:00"), pd.Timestamp("2025-01-09"), comp)
    assert f["comp_n"] == 0 and np.isnan(f["comp_min_fare"])  # nothing invented


def test_time_split_trains_on_older_and_beats_nothing_silently():
    rng = np.random.default_rng(0)
    n = 100
    df = pd.DataFrame(dict(route_id=rng.choice(["A", "B"], n), booking_time=pd.date_range("2025-01-01", periods=n),
                           fare_on_sale=rng.integers(300, 600, n), flag_cancelled=False))
    for c in fare_model.COLUMN_MAP:
        df[c] = df.get(c, rng.random(n))
    df["ac"] = rng.integers(0, 2, n)
    df["sleeper"] = rng.integers(0, 2, n)
    b = fare_model.train(df)
    assert b["metrics"]["n_train"] == 80 and b["metrics"]["n_test"] == 20
    assert pd.Timestamp(b["metrics"]["split_date"]) == df["booking_time"].iloc[80]  # test is the newest
    assert {"mae_model", "mae_route_median_baseline"} <= b["metrics"].keys()


def test_prediction_has_ordered_range_flag_and_version():
    c = TestClient(app)
    r = c.post("/fare/predict", json=dict(route_id="R001", departure_at="2026-03-01T08:00", available_seats=20, ac=1, sleeper=0,
                                          as_of="2026-02-20T00:00", engine_fare=500)).json()
    assert r["fare_low"] <= r["fare_mid"] <= r["fare_high"]
    assert r["model_version"] and "insufficient_data" in r and r["gap_to_engine"] == r["fare_mid"] - 500
    assert "Reference only" in r["note"]
    assert c.post("/fare/predict", json=dict(route_id="ZZ", departure_at="2026-03-01T08:00", available_seats=1, ac=0, sleeper=0)).status_code == 404


def test_service_fare_prediction_endpoint():
    c = TestClient(app)
    r = c.get("/services/BKG2023011/fare-prediction").json()
    assert r["fare_low"] <= r["fare_mid"] <= r["fare_high"] and r["engine_fare"] == 385
    assert c.get("/services/NOPE/fare-prediction").status_code == 404


def test_no_coach_type_means_no_prediction_not_a_guess():
    b = fare_model.load()
    f = pd.DataFrame([dict(route_id="R001", ac=np.nan, sleeper=np.nan, comp_n=0, **{
        c: 1.0 for c in fare_model.COLUMN_MAP if c not in ("route_id", "ac", "sleeper")})])
    p = fare_model.predict(b, f).iloc[0]
    assert np.isnan(p["fare_mid"]) and p["insufficient_data"]
