import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import fare_model, main
from app.db import engine
from scripts.train_fare_model import train


def _services(n_per_year=12):
    """A small route table where fare = route base + 40 per year + 100 on a holiday - 3 per seat left."""
    rows = []
    for route, base in (("R1", 400), ("R2", 700)):
        for year in (2023, 2024, 2025):
            for i in range(n_per_year):
                seats, holiday = 5 + i, (0.0, 0.5, 1.0)[i % 3]
                rows.append(dict(route_id=route, departure_at=pd.Timestamp(f"{year}-03-{i + 1:02d} 08:00"),
                                 available_seats=seats, holiday_score=holiday, flag_cancelled=False,
                                 fare_on_sale=base + 40 * (year - 2023) + 100 * holiday - 3 * seats))
    return pd.DataFrame(rows)


def test_inputs_are_route_seats_holiday_weekend_and_year():
    x = fare_model.features(pd.DataFrame([dict(route_id="R1", departure_at="2026-11-06 22:00", available_seats=8,
                                               holiday_score=0.5)]))
    assert x.iloc[0].to_dict() == dict(route_id="R1", available_seats=8.0, holiday_score=0.5, weekend=1, year=2026)
    assert fare_model.features(pd.DataFrame([dict(route_id="R1", departure_at="2026-11-09 22:00", available_seats=8,
                                                  holiday_score=0)]))["weekend"].iloc[0] == 0


def test_training_learns_the_year_and_reports_accuracy():
    s = _services()
    s.loc[0, "flag_cancelled"] = True
    b = train(s)
    assert b["rows"] == len(s) - 1 and b["routes"] == ["R1", "R2"] and b["future_year"] == 2025
    assert b["cv_mae"] < 1 and b["future_mae"] < 1 and b["half_width"] < 1
    p = fare_model.predict(b, pd.DataFrame([dict(route_id="R1", departure_at="2026-03-02", available_seats=10,
                                                 holiday_score=0)])).iloc[0]
    assert p["fare_mid"] == pytest.approx(400 + 120 - 30, abs=1)  # 2026 is beyond the data: the yearly rise continues


def test_unknown_route_or_missing_input_gets_no_prediction():
    b = train(_services())
    rows = pd.DataFrame([dict(route_id="R9", departure_at="2025-03-02", available_seats=10, holiday_score=0),
                         dict(route_id="R1", departure_at="2025-03-02", available_seats=np.nan, holiday_score=0)])
    p = fare_model.predict(b, rows)
    assert p["insufficient_data"].all() and p["fare_mid"].isna().all()


def test_range_is_mid_plus_minus_half_width_and_never_below_zero():
    b = dict(train(_services()), half_width=50.0)
    p = fare_model.predict(b, pd.DataFrame([dict(route_id="R1", departure_at="2024-03-02", available_seats=10,
                                                 holiday_score=0)])).iloc[0]
    assert p["fare_high"] - p["fare_mid"] == 50 and p["fare_mid"] - p["fare_low"] == 50
    b["half_width"] = 10_000.0
    assert fare_model.predict(b, pd.DataFrame([dict(route_id="R1", departure_at="2024-03-02", available_seats=10,
                                                    holiday_score=0)]))["fare_low"].iloc[0] == 0


def test_saved_model_predicts_every_real_service():
    b = fare_model.load()
    assert b["routes"] == ["R001", "R002", "R003", "R004", "R005"] and b["half_width"] > 0
    s = pd.read_sql_table("services", engine)
    s.columns = [str(c) for c in s.columns]
    p = fare_model.predict(b, s)
    assert not p["insufficient_data"].any() and (p["fare_low"] <= p["fare_mid"]).all()


@pytest.fixture()
def client():
    return TestClient(main.app)


def test_fare_checker_api(client):
    body = dict(route_id="R004", departure_at="2026-11-13T08:00", available_seats=20)
    plain = client.post("/fare/predict", json=body).json()
    holiday = client.post("/fare/predict", json={**body, "holiday_score": 1}).json()
    assert plain["fare_low"] < plain["fare_mid"] < plain["fare_high"] and holiday["fare_mid"] > plain["fare_mid"]
    assert plain["holiday_score"] == 0 and "AC" not in str(plain)
    assert client.post("/fare/predict", json={**body, "route_id": "R9"}).status_code == 404
    assert client.post("/fare/predict", json={**body, "holiday_score": 2}).status_code == 422
    assert client.post("/fare/predict", json={**body, "available_seats": -1}).status_code == 422
