import numpy as np
import pandas as pd

from app import fare_model, fare_notebook
from app.db import engine


def _comp():
    return pd.DataFrame(dict(route_id=["R1", "R1", "R1", "R2"], fare=[300.0, 400.0, 500.0, 900.0],
                             captured_at=pd.to_datetime(["2023-01-01", "2023-01-02", "2030-01-01", "2023-01-01"])))


def test_route_stats_follow_the_notebook():
    s = fare_notebook.route_stats(_comp()).set_index("route_id")
    assert s.loc["R1", "comp_min_fare"] == 300 and s.loc["R1", "comp_median_fare"] == 400
    assert s.loc["R1", "comp_avg_fare"] == 400 and s.loc["R1", "comp_n"] == 3 and s.loc["R2", "comp_n"] == 1


def test_competitor_rows_are_not_cut_off_by_capture_time_unlike_fare_model():
    svc = pd.DataFrame([dict(service_id="S", route_id="R1", duration_hours=5.0, flag_cancelled=False)])
    f = fare_notebook.build_features(svc, _comp())
    assert f.loc[0, "comp_n"] == 3 and f.loc[0, "comp_min_fare"] == 300  # the 2030 row is included, by design
    unknown = fare_notebook.build_features(svc.assign(route_id="R9"), _comp())
    assert unknown.loc[0, "comp_n"] == 0 and np.isnan(unknown.loc[0, "comp_min_fare"])


def test_missing_duration_is_filled_from_the_same_route_only():
    svc = pd.DataFrame([dict(service_id="A", route_id="R1", duration_hours=4.0), dict(service_id="B", route_id="R1", duration_hours=np.nan),
                        dict(service_id="C", route_id="R2", duration_hours=9.0)])
    f = fare_notebook.build_features(svc, _comp()).set_index("service_id")
    assert f.loc["B", "duration_hours"] == 4.0


def test_real_predictions_have_ordered_ranges_and_no_guessed_coach_type():
    services = pd.read_sql_table("services", engine)
    feats = fare_notebook.build_features(services, pd.read_sql_table("competitor_fares", engine))
    p = fare_notebook.predict(fare_notebook.load(), feats)
    ok = p["fare_mid"].notna()
    assert ok.sum() >= 200
    assert (p.loc[ok, "fare_low"] <= p.loc[ok, "fare_mid"]).all() and (p.loc[ok, "fare_mid"] <= p.loc[ok, "fare_high"]).all()
    assert ok.equals(feats[fare_model.NEEDED].notna().all(axis=1))  # no AC / Sleeper means no prediction
    assert fare_notebook.load()["version"] == fare_notebook.MODEL_VERSION and "70.87" in fare_notebook.load()["range_basis"]


def test_predict_for_one_service():
    services = pd.read_sql_query("SELECT * FROM services WHERE route_id = 'R001'", engine, parse_dates=["booking_time", "departure_at"])
    comp = pd.read_sql_query("SELECT * FROM competitor_fares WHERE route_id = 'R001'", engine)
    p = fare_notebook.predict_for_service(services, comp, "BKG2023011")
    assert p and p["low"] <= p["mid"] <= p["high"] and p["competitor_rows_used"] > 0
    assert fare_notebook.predict_for_service(services, comp, "NOPE") is None
