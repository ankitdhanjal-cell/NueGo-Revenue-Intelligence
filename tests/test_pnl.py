import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.pnl import add_expected_margin, compute_pnl, totals


def _svc(**kw):
    base = dict(service_id="S1", route_id="R1", origin="Delhi", destination="Agra",
                departure_at=pd.Timestamp("2025-01-10 08:00"), booking_status="Confirmed",
                seats_sold=10, total_seats=40, fare_on_sale=500, distance_km=200,
                coach_cost_per_km=40.0, days_to_go=5.0, crew_cost=30000, duration_hours=5.0, tolls=500, flag_cancelled=False,
                refund_amount=0)
    base.update(kw)
    return pd.DataFrame([base])


def test_confirmed_service_arithmetic():
    r = compute_pnl(_svc(), trips_per_month=30).iloc[0]
    assert r["revenue"] == 5000
    assert r["cost_to_run"] == 200 * 40 + 1000 + 500  # crew 30000/30 = 1000 -> 9500
    assert r["profit"] == -4500
    assert r["breakeven_fare_current_seats"] == 950
    assert r["breakeven_fare_full_coach"] == 9500 / 40
    assert pd.isna(r["marginal_floor"])


def test_cancelled_refund_reduces_revenue_with_floor():
    r = compute_pnl(_svc(booking_status="Cancelled", flag_cancelled=True, refund_amount=1200)).iloc[0]
    assert r["revenue"] == 3800
    r = compute_pnl(_svc(booking_status="Cancelled", flag_cancelled=True, refund_amount=99999)).iloc[0]
    assert r["revenue"] == 0


def test_crew_split_adds_back_to_monthly_total():
    # 30 trips with different durations: the split parts must sum to the source within 0.5%
    s = pd.concat([_svc(service_id=f"S{i}", duration_hours=h)
                   for i, h in enumerate([4.0, 6.0] * 15)], ignore_index=True)
    s["route_id"] = "R1"
    split = compute_pnl(s, trips_per_month=30)["crew_cost_split"].sum()
    assert abs(split - 30000) / 30000 < 0.005


def test_missing_duration_taken_from_same_route_and_flagged():
    s = pd.concat([_svc(), _svc(service_id="S2", duration_hours=float("nan"))], ignore_index=True)
    p = compute_pnl(s, trips_per_month=30)
    assert p.loc[1, "flag_duration_from_route"] and p.loc[1, "crew_cost_split"] == 1000


def test_zero_seats_has_no_margin_or_floor():
    r = compute_pnl(_svc(seats_sold=0)).iloc[0]
    assert pd.isna(r["margin_pct"]) and pd.isna(r["breakeven_fare_current_seats"])


def test_totals_sum_matches():
    p = compute_pnl(pd.concat([_svc(), _svc(service_id="S2")]))
    t = totals(p, "corridor")
    assert t.loc[0, "services"] == 2 and t.loc[0, "profit"] == p["profit"].sum()
    c = compute_pnl(pd.concat([_svc(), _svc(service_id="S2", flag_cancelled=True)]))
    assert totals(c, "corridor").loc[0, "services"] == 1  # cancelled left out


def test_api():
    c = TestClient(app)
    assert c.get("/pnl/services/NOPE").status_code == 404
    assert c.get("/pnl/totals?group_by=channel").status_code == 422
    assert c.get("/pnl/totals?group_by=bogus").status_code == 422
    assert c.get("/pnl/totals?group_by=corridor").status_code == 200
    assert c.get("/pnl/cancelled").status_code == 200


def test_expected_margin_range_and_missing_inputs():
    p = compute_pnl(pd.concat([_svc(), _svc(service_id="S2")], ignore_index=True), trips_per_month=30)
    f = pd.DataFrame([dict(service_id="S1", expected_low=2.0, expected_mid=10.0, expected_high=20.0,
                           insufficient_data=False)])
    e = add_expected_margin(p, f)
    r = e.iloc[0]  # cost 9500, fare 500
    assert (r["expected_revenue_low"], r["expected_revenue_mid"], r["expected_revenue_high"]) == (1000, 5000, 10000)
    assert r["expected_margin_low"] == -8500 and r["expected_margin_high"] == 500
    assert r["expected_margin_low"] <= r["expected_margin_mid"] <= r["expected_margin_high"]
    assert pd.isna(e.iloc[1]["expected_margin_mid"]) and e.iloc[1]["forecast_insufficient_data"]  # no forecast -> NaN


def test_missing_cost_marks_margin_cost_missing():
    p = compute_pnl(_svc(tolls=float("nan")), trips_per_month=30)
    assert p.iloc[0]["margin_status"] == "cost missing" and pd.isna(p.iloc[0]["profit"])


def test_average_floor_uses_expected_seats_and_floor_in_use_is_recorded():
    p = compute_pnl(pd.concat([_svc(), _svc(service_id="S2", days_to_go=0.5)], ignore_index=True), trips_per_month=30)
    f = pd.DataFrame([dict(service_id=i, expected_low=5.0, expected_mid=10.0, expected_high=19.0,
                           insufficient_data=False) for i in ("S1", "S2")])
    e = add_expected_margin(p, f)
    r = e.iloc[0]  # cost 9500
    assert r["average_floor_mid"] == 950 and r["average_floor_high"] == 9500 / 5 and r["average_floor_low"] == 500
    assert r["floor_in_use"] == "average" and e.iloc[1]["floor_in_use"].startswith("marginal")
    assert r["floor_switch_hours"] == 24


# ---- real-data checks (need the tables built by the pipeline scripts) ----
def test_real_totals_equal_sum_of_services():
    from app.db import engine
    pnl = pd.read_sql_table("pnl_services", engine)
    live = pnl[~pnl["flag_cancelled"]]
    for g in ("corridor", "date"):
        t = totals(pnl, g)
        assert t["services"].sum() == len(live)
        assert abs(t["revenue"].sum() - live["revenue"].sum()) < 0.01
        assert abs(t["cost_to_run"].sum() - live["cost_to_run"].sum()) < 0.01
        assert abs(t["profit"].sum() - live["profit"].sum()) < 0.01


def test_real_crew_split_adds_back_to_monthly_source_within_half_percent():
    """A route-month with N trips: the split parts must sum to the monthly crew total."""
    from app.config import TRIPS_PER_ROUTE_MONTH as N
    from app.db import engine
    s = pd.read_sql_table("services", engine)
    p = pd.read_sql_table("pnl_services", engine)
    s["split"] = s["service_id"].map(p.set_index("service_id")["crew_cost_split"])
    s["year"] = s["departure_at"].dt.year
    for (route, year), g in s.groupby(["route_id", "year"]):
        monthly = g["crew_cost"].iloc[0]  # one crew total per route and year in the data
        assert abs(g["split"].mean() * N - monthly) / monthly < 0.005, (route, year)
