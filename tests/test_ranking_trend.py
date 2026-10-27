import csv
import re
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.pnl import rank, trend

RAW = Path(__file__).resolve().parents[1] / "data/raw/route_details.csv"


def _pnl(rows):
    base = dict(route_id="R1", departure_at=pd.Timestamp("2025-01-10 08:00"), seats_sold=10, total_seats=40,
                cost_to_run=10000.0, expected_margin_mid=-5000.0, flag_cancelled=False,
                margin_status="ok", checkpoint_status="ok", revenue=5000.0, profit=-5000.0)
    return pd.DataFrame([{**base, **r} for r in rows])


def _fc(ids, mid=20.0):
    return pd.DataFrame(dict(service_id=ids, expected_mid=mid))


def test_rank_orders_by_score_and_ties_go_to_earliest_departure():
    p = _pnl([dict(service_id="A", departure_at=pd.Timestamp("2025-01-12")),
              dict(service_id="B", departure_at=pd.Timestamp("2025-01-11")),
              dict(service_id="C", seats_sold=2, expected_margin_mid=-9000.0)])
    ranked, _ = rank(p, _fc(["A", "B", "C"]), 0.5, 0.5)
    assert list(ranked["service_id"]) == ["C", "B", "A"]  # C worst; A/B tie -> B departs earlier
    again, _ = rank(p.sample(frac=1, random_state=3), _fc(["A", "B", "C"]), 0.5, 0.5)
    assert list(again["service_id"]) == list(ranked["service_id"])  # deterministic


def test_rank_excludes_cancelled_cost_missing_and_no_forecast():
    p = _pnl([dict(service_id="A"), dict(service_id="B", flag_cancelled=True),
              dict(service_id="C", margin_status="cost missing"), dict(service_id="D")])
    ranked, ex = rank(p, _fc(["A", "B", "C"]), 0.5, 0.5)
    assert list(ranked["service_id"]) == ["A"]
    assert dict(zip(ex["service_id"], ex["excluded_reason"])) == {"B": "cancelled", "C": "cost missing", "D": "no forecast"}


def test_trend_same_weekday_within_8_weeks_and_no_history_flag():
    p = _pnl([dict(service_id="NOW", departure_at=pd.Timestamp("2025-03-10 08:00")),   # Monday
              dict(service_id="W1", departure_at=pd.Timestamp("2025-03-03 08:00")),     # Monday, in window
              dict(service_id="W2", departure_at=pd.Timestamp("2025-03-04 08:00")),     # Tuesday
              dict(service_id="OLD", departure_at=pd.Timestamp("2024-12-01 08:00"))])   # outside window
    t = trend(p, "NOW")
    assert t["services_found"] == 1 and t["trend_available"] and t["checkpoint_status"] == "ok"
    t = trend(p, "OLD")
    assert t["services_found"] == 0 and t["checkpoint_status"] == "no history"


def test_hand_check_revenue_matches_independent_calculation_for_20_services():
    """FR-PNL-001: recompute revenue from the raw CSV text (no pandas, no shared cleaning code)."""
    money = lambda v: float(re.sub(r"[^\d.]", "", v) or 0)
    rows = list(csv.DictReader(open(RAW, encoding="utf-8")))[::12][:20]
    assert len(rows) == 20
    api = TestClient(app)
    for r in rows:
        sold = int(r["Total Seats"]) - int(r["Available Seats"])
        expected = sold * money(r["Fare on Sale (INR)"])
        if r["Booking Status"] == "Cancelled":
            expected = max(expected - money(r["Refund Amount (INR)"]), 0)
        got = api.get(f"/pnl/services/{r['Booking ID']}").json()["revenue"]
        assert got == expected, r["Booking ID"]


def test_api_ranking_and_trend():
    c = TestClient(app)
    r = c.get("/pnl/ranking?limit=5").json()
    assert len(r["ranked"]) == 5 and r["ranked"][0]["rank"] == 1
    assert r["ranked"][0]["score"] >= r["ranked"][1]["score"]
    assert {"cancelled", "no forecast"} <= set(r["excluded_by_reason"])
    assert c.get("/pnl/services/BKG2023011/trend").status_code == 200
    assert c.get("/pnl/services/NOPE/trend").status_code == 404


def test_no_history_service_gets_no_behind_score_but_keeps_margin_part():
    p = _pnl([dict(service_id="A", checkpoint_status="no history"), dict(service_id="B")])
    ranked, _ = rank(p, _fc(["A", "B"]), 0.5, 0.5)
    a = ranked[ranked["service_id"] == "A"].iloc[0]
    assert a["behind_part"] == 0 and a["margin_part"] > 0 and a["checkpoint_status"] == "no history"
