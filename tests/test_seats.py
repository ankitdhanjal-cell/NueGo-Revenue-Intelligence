import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app import seat_model
from app.main import app


def _df(n=100):
    rng = np.random.default_rng(1)
    df = pd.DataFrame(dict(route_id=rng.choice(["A", "B"], n), booking_time=pd.date_range("2025-01-01", periods=n),
                           seats_sold=rng.integers(0, 40, n), days_to_go=rng.random(n) * 10, flag_cancelled=False,
                           ac=rng.integers(0, 2, n), sleeper=rng.integers(0, 2, n), total_seats=40))
    for c in seat_model.COLUMN_MAP:
        if c not in df:
            df[c] = rng.random(n)
    return df


def test_time_split_and_baseline_reported():
    b = seat_model.train(_df())
    m = b["metrics"]
    assert m["n_train"] == 80 and m["n_test"] == 20
    assert {"mae_model", "mae_route_mean_baseline", "mae_with_days_to_go", "corr_seats_vs_days_to_go"} <= m.keys()


def test_prediction_range_is_ordered_and_within_capacity():
    df = _df()
    b = seat_model.train(df)
    b["model"] = seat_model.make_model().fit(seat_model.model_frame(df), df["seats_sold"])
    p = seat_model.predict(b, df)
    assert (p["expected_low"] <= p["expected_mid"]).all() and (p["expected_mid"] <= p["expected_high"]).all()
    assert (p["expected_high"] <= 40).all() and (p["expected_low"] >= 0).all()


def test_no_coach_type_means_no_prediction():
    df = _df(30)
    df.loc[0, "ac"] = np.nan
    b = seat_model.train(_df())
    b["model"] = seat_model.make_model().fit(seat_model.model_frame(_df()), _df()["seats_sold"])
    p = seat_model.predict(b, df)
    assert np.isnan(p.loc[0, "expected_mid"]) and p.loc[0, "insufficient_data"]


def test_api_returns_range_flag_and_no_invented_curve():
    c = TestClient(app)
    r = c.get("/forecast/services/BKG2023011/curve").json()
    e = r["expected_seats_sold"]
    assert e["low"] <= e["mid"] <= e["high"] and r["curve"] is None and r["curve_note"]
    assert "behind_checkpoint" in r and r["model_version"]
    assert c.get("/forecast/services/NOPE/curve").status_code == 404
