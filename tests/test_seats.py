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


def test_range_from_models_own_errors_and_capacity():
    class Const:
        def predict(self, X):
            return np.full(len(X), 20.0)
    df = _df()
    b = seat_model.make_bundle(Const(), df)
    p = seat_model.predict(b, df)
    assert (p["expected_low"] <= p["expected_mid"]).all() and (p["expected_mid"] <= p["expected_high"]).all()
    assert (p["expected_high"] <= 40).all() and (p["expected_low"] >= 0).all() and "in-sample" in b["range_basis"]


def test_no_coach_type_means_no_prediction():
    df = _df(30)
    df.loc[0, "ac"] = np.nan
    class Const:
        def predict(self, X):
            return np.full(len(X), 20.0)
    b = seat_model.make_bundle(Const(), _df())
    p = seat_model.predict(b, df)
    assert np.isnan(p.loc[0, "expected_mid"]) and p.loc[0, "insufficient_data"]


def test_api_returns_range_flag_and_no_invented_curve():
    c = TestClient(app)
    r = c.get("/forecast/services/BKG2023011/curve").json()
    e = r["expected_seats_sold"]
    assert e["low"] <= e["mid"] <= e["high"] and r["curve"] is None and r["curve_note"]
    assert "behind_checkpoint" in r and r["model_version"]
    assert c.get("/forecast/services/NOPE/curve").status_code == 404
