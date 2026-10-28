import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import curve, main


def _services(n_past=10, route="R1"):
    """n_past earlier Monday-morning services (dtg 5 -> band 3-7) plus the one we ask about."""
    rows = [dict(service_id=f"P{i}", route_id=route, departure_at=pd.Timestamp("2026-04-06 07:00") + pd.Timedelta(days=7 * i),
                 days_to_go=5.0, holiday_score=0.0, seats_sold=10.0 + i, total_seats=40, flag_cancelled=False)
            for i in range(n_past)]
    rows.append(dict(service_id="NOW", route_id=route, departure_at=pd.Timestamp("2026-08-03 07:00"),
                     days_to_go=5.0, holiday_score=0.0, seats_sold=12.0, total_seats=40, flag_cancelled=False))
    return pd.DataFrame(rows)


def _extras(df, sid="NOW"):
    return curve.curve_extras(df[df["service_id"] == sid], df[df["service_id"] != sid])


def test_band_is_ordered_and_uses_past_services_only():
    e = _extras(_services(10))
    b = e["band"]
    assert e["band_status"] == "ok" and b["n"] == 10 and b["p10"] <= b["p50"] <= b["p90"]
    assert e["actual"]["points"] == [dict(days_to_go=5.0, seats_sold=12.0)] and e["capacity"] == 40


def test_later_services_are_not_history():
    df = _services(10)
    df.loc[df["service_id"] == "P9", "departure_at"] = pd.Timestamp("2026-12-07 07:00")  # after NOW
    assert _extras(df)["band"]["n"] == 9


def test_fewer_than_four_similar_services_is_no_history():
    e = _extras(_services(3))
    assert e["band"] is None and e["band_status"] == "no history"
    assert all(c["status"] == "no history" for c in e["checkpoints"] if c["dtg_band"] == "3-7")


def test_other_route_and_cancelled_are_ignored():
    df = _services(6)
    df.loc[df["service_id"].isin(["P0", "P1", "P2"]), "flag_cancelled"] = True
    df.loc[df["service_id"] == "P3", "route_id"] = "R2"
    assert _extras(df)["band_status"] == "no history"  # 2 left


def test_checkpoints_cover_every_dtg_band():
    assert [c["dtg_band"] for c in _extras(_services(10))["checkpoints"]] == ["0-3", "3-7", "7-14", "14+"]


def test_route_helper_adds_forecast_and_flags(monkeypatch):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    _services(10).to_sql("services", eng, index=False)
    monkeypatch.setattr(main, "engine", eng)
    r = dict(route_id="R1", expected_low=8.0, expected_mid=14.0, expected_high=20.0, insufficient_data=False)
    out = main.curve_extras_for("NOW", r)
    assert out["forecast_to_departure"]["seats"] == dict(low=8.0, mid=14.0, high=20.0)
    assert out["band_status"] == "ok" and out["flags"] == {"no_history": False, "insufficient_data": False}


def test_api_keeps_module_a_fields_and_adds_new_ones():
    r = TestClient(main.app).get("/forecast/services/BKG2023011/curve").json()
    for key in ("expected_seats_sold", "actual_seats_sold", "behind_checkpoint", "observed_points", "insufficient_data",
                "days_to_go_at_snapshot", "gap_to_expected", "model_version"):
        assert key in r
    assert r["curve"] is None and r["curve_note"]  # no shape is invented
    assert r["flags"].keys() == {"no_history", "insufficient_data"} and len(r["checkpoints"]) == 4
    assert r["forecast_to_departure"]["seats"] == r["expected_seats_sold"]
