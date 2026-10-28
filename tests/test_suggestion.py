import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import main, reasons, suggestion
from app.rules import RuleContext, check_fare


def _svc(**changes):
    base = dict(service_id="S1", route_id="R1", fare_on_sale=500.0, cost_to_run=15000.0, margin_status="ok",
                flag_cancelled=False, checkpoint_status="ok", hours_to_departure=100.0, marginal_floor=float("nan"),
                average_floor_low=380.0, average_floor_mid=450.0, average_floor_high=600.0, seats_sold=20.0,
                holiday_score=0.0, holiday_event="No major holiday noted", avg_rating=4.0, num_ratings=500,
                rival_median=None, predicted_fare=dict(low=450.0, mid=520.0, high=590.0, label="linear regression prediction"))
    return {**base, **changes}


def _rules(**changes):
    base = dict(version=1, floor_switch_hours=24.0, ceiling=1500.0, state_cap=None, max_change_pct=15.0,
                min_minutes_between_changes=240, seats_weight=0.0,
                fare_steps=[float(x) for x in range(200, 1501, 10)])
    return {**base, **changes}


def falling(fares):
    """Stub seat model: seats fall as the fare rises (a trusted price response). Ranges are ordered."""
    return {f: dict(low=max(0, 30 - f / 40 - 3), mid=max(0, 30 - f / 40), high=min(40, 30 - f / 40 + 3)) for f in fares}


def flat(fares):
    return {f: dict(low=15.0, mid=20.0, high=25.0) for f in fares}


def rising(fares):
    """Like the real team model in this data: more fare, more seats."""
    return {f: dict(low=f / 40 - 3, mid=f / 40, high=min(40, f / 40 + 3)) for f in fares}


def _run(svc=None, rules=None, seat_fn=falling, band=None, rivals=None, minutes=None):
    return suggestion.build_suggestion(svc or _svc(), rules or _rules(), seat_fn, band, rivals or [], minutes)


# ---- the hard rules -----------------------------------------------------------------------------
@pytest.mark.parametrize("seat_fn", [falling, flat, rising])
def test_suggestion_always_passes_every_rule_over_random_contexts(seat_fn):
    rng = np.random.default_rng(7)
    made = 0
    for _ in range(300):
        fare = float(rng.choice(range(300, 900, 10)))
        svc = _svc(fare_on_sale=fare, average_floor_mid=float(rng.integers(200, 900)))
        rules = _rules(ceiling=float(rng.integers(300, 1000)), max_change_pct=float(rng.choice([5, 15, 50, 100])),
                       state_cap=None if rng.random() < 0.5 else float(rng.integers(300, 1000)),
                       seats_weight=float(rng.choice([0, 20])))
        minutes = None if rng.random() < 0.7 else float(rng.integers(0, 600))
        out = _run(svc, rules, seat_fn, minutes=minutes)
        if out["suggested_fare"] is None:
            continue
        made += 1
        ctx = RuleContext(fare, out["floor_value"], rules["ceiling"], rules["state_cap"], rules["max_change_pct"],
                          rules["min_minutes_between_changes"], minutes, rules["fare_steps"])
        assert check_fare(out["suggested_fare"], ctx) == []
    assert made > 20


def test_ranges_are_ordered_and_margin_is_revenue_minus_cost():
    out = _run()
    for k in ("expected_revenue", "expected_margin"):
        assert out[f"{k}_low"] <= out[f"{k}_mid"] <= out[f"{k}_high"]
    s = out["expected_seats"]
    assert s["low"] <= s["mid"] <= s["high"]
    assert out["expected_margin_mid"] == pytest.approx(out["expected_revenue_mid"] - out["cost_to_run"], abs=0.02)
    c = out["change_vs_current"]
    assert c["extra_seats"]["low"] <= c["extra_seats"]["mid"] <= c["extra_seats"]["high"]
    assert c["margin_change"]["low"] <= c["margin_change"]["mid"] <= c["margin_change"]["high"]


# ---- who gets no suggestion ---------------------------------------------------------------------
def test_cancelled_service_gets_no_suggestion():
    out = _run(_svc(flag_cancelled=True))
    assert out["suggested_fare"] is None and out["blocked_reason"] == "CANCELLED" and out["reasons"] == []


@pytest.mark.parametrize("svc", [_svc(cost_to_run=float("nan")), _svc(margin_status="cost missing")])
def test_cost_missing_returns_null_with_flag(svc):
    out = _run(svc)
    assert out["suggested_fare"] is None and out["blocked_reason"] == "COST_MISSING" and out["flags"]["cost_missing"]


def test_no_floor_available_returns_null():
    out = _run(_svc(average_floor_mid=float("nan")))
    assert out["blocked_reason"] == "NO_FLOOR" and out["flags"]["floor_missing"]


def test_no_seat_forecast_returns_null_and_flags_insufficient_data():
    out = _run(seat_fn=lambda fares: None)
    assert out["blocked_reason"] == "NO_SEAT_FORECAST" and out["flags"]["insufficient_data"]


def test_floor_above_every_allowed_fare_is_blocked_with_detail():
    out = _run(_svc(average_floor_mid=900.0))
    assert out["suggested_fare"] is None and out["blocked_reason"] == "NO_ALLOWED_FARE"
    d = out["blocked_detail"]
    assert d["floor_value"] == 900.0 and d["highest_fare_allowed_ignoring_floor"] == 570.0  # 500 + 15%, on a step


def test_no_checkpoint_history_still_gets_a_suggestion_marked_no_history():
    out = _run(_svc(checkpoint_status="no history"))
    assert out["suggested_fare"] is not None and out["checkpoint_status"] == "no history" and out["flags"]["no_history"]


# ---- floors -------------------------------------------------------------------------------------
def test_far_from_departure_uses_average_floor():
    out = _run(_svc(hours_to_departure=100.0, marginal_floor=480.0))
    assert out["floor_in_use"] == "average" and out["floor_value"] == 450.0 and not out["flags"]["floor_missing"]


def test_close_to_departure_uses_marginal_floor_when_it_exists():
    out = _run(_svc(hours_to_departure=10.0, marginal_floor=480.0))
    assert out["floor_in_use"] == "marginal" and out["floor_value"] == 480.0
    assert out["suggested_fare"] >= 480.0


def test_close_to_departure_with_missing_marginal_falls_back_to_average_and_flags_it():
    out = _run(_svc(hours_to_departure=10.0))
    assert out["floor_in_use"].startswith("average (marginal floor missing") and out["floor_value"] == 450.0
    assert out["flags"]["floor_missing"] and out["suggested_fare"] >= 450.0


def test_switch_point_comes_from_the_rules_row():
    svc = _svc(hours_to_departure=30.0, marginal_floor=480.0)
    assert _run(svc, _rules(floor_switch_hours=24.0))["floor_in_use"] == "average"
    assert _run(svc, _rules(floor_switch_hours=48.0))["floor_in_use"] == "marginal"


# ---- rule changes take effect -------------------------------------------------------------------
def test_a_lowered_ceiling_changes_the_next_suggestion():
    assert _run(rules=_rules(ceiling=1500.0))["suggested_fare"] is not None
    assert _run(rules=_rules(ceiling=440.0))["blocked_reason"] == "NO_ALLOWED_FARE"  # floor 450 > ceiling


def test_state_cap_and_step_size_limit_the_choice():
    out = _run(_svc(fare_on_sale=500.0, average_floor_mid=200.0), _rules(state_cap=520.0), seat_fn=rising)
    assert out["suggested_fare"] <= 520.0
    out = _run(_svc(fare_on_sale=500.0, average_floor_mid=200.0), _rules(max_change_pct=2.0), seat_fn=rising)
    assert 490.0 <= out["suggested_fare"] <= 510.0


def test_too_soon_after_last_change_only_current_fare_is_allowed():
    out = _run(minutes=30.0)  # current 500 is a fare step
    assert out["suggested_fare"] == 500.0 and not out["flags"]["last_change_unknown"]
    assert _run(_svc(fare_on_sale=505.0), minutes=30.0)["blocked_reason"] == "NO_ALLOWED_FARE"  # not a step
    assert _run(minutes=None)["flags"]["last_change_unknown"]


# ---- which fare is chosen -----------------------------------------------------------------------
def test_choice_is_the_allowed_fare_closest_to_the_predicted_fare_and_ties_go_lower():
    assert suggestion.choose_fare([380.0, 400.0, 420.0], 405.0) == 400.0
    assert suggestion.choose_fare([380.0, 400.0], 390.0) == 380.0  # equally close: the lower fare
    assert {suggestion.choose_fare([380.0, 400.0], 390.0) for _ in range(5)} == {380.0}  # deterministic

def test_trusted_price_response_allows_a_change_claim():
    out = _run(_svc(fare_on_sale=500.0, average_floor_mid=200.0), seat_fn=falling)
    assert out["price_response"] == "used" and out["change_vs_current"] is not None
    assert out["flags"]["price_response_not_reliable"] is False

def test_the_predicted_fare_sets_the_price_whatever_the_seat_model_says():
    svc = _svc(average_floor_mid=200.0)  # predicted mid 520, current 500, 15% window
    for seat_fn in (falling, flat, rising):
        assert _run(svc, seat_fn=seat_fn)["suggested_fare"] == 520.0
    assert _run(_svc(average_floor_mid=200.0, predicted_fare=dict(low=1.0, mid=900.0, high=2.0, label="x")))["suggested_fare"] == 570.0  # capped by the 15% step limit

def test_untrusted_price_response_never_claims_a_gain():
    out = _run(seat_fn=rising)
    assert out["price_response"] == "not_reliable" and out["change_vs_current"] is None
    assert out["flags"]["price_response_not_reliable"] and out["suggested_fare"] == 520.0
    assert _run(seat_fn=flat)["price_response"] == "not_reliable"


def test_a_single_allowed_fare_is_not_assessed():
    out = _run(rules=_rules(max_change_pct=1.0), seat_fn=falling)  # only 500 within 1%
    assert out["price_response"] == "not_assessed" and out["change_vs_current"] is None


def test_no_prediction_means_no_suggestion_and_the_prediction_is_always_returned():
    assert _run(_svc(predicted_fare=None))["blocked_reason"] == "NO_FARE_PREDICTION"
    assert _run(_svc(predicted_fare=None))["flags"]["insufficient_data"]
    blocked = _run(_svc(average_floor_mid=900.0))  # no allowed fare, but the model's fare is still shown
    assert blocked["blocked_reason"] == "NO_ALLOWED_FARE" and blocked["predicted_fare"]["mid"] == 520.0

# ---- reasons ------------------------------------------------------------------------------------
def _r(**kw):
    a = dict(fare=500.0, seats_sold=20.0, band=None, rival_median=None, holiday_score=0.0, holiday_event="x",
             floor_limited=False, floor=450.0, rating=4.0, rating_count=100)
    return reasons.build_reasons(**{**a, **kw})


BAND = dict(p10=15.0, p50=20.0, p90=25.0, n=10)


def test_pace_behind_and_ahead_use_p10_and_p90():
    assert _r(seats_sold=10.0, band=BAND)[0] == dict(code="BOOKING_PACE", text="10 seats behind checkpoint")
    assert _r(seats_sold=30.0, band=BAND)[0]["text"] == "10 seats ahead of checkpoint"


def test_fallback_is_booking_pace_on_pace_or_no_history():
    assert _r(band=BAND) == [dict(code="BOOKING_PACE", text="On pace with similar past services")]
    assert _r(band=None)[0]["text"] == "No checkpoint history yet, pace not assessed"


def test_rival_gap_needs_more_than_10_percent():
    assert _r(rival_median=480.0)[0]["code"] == "BOOKING_PACE"  # 4.2%: not triggered
    got = _r(rival_median=400.0)
    assert got[0]["code"] == "RIVAL_GAP" and "25% above the median rival fare (INR 400)" in got[0]["text"]


def test_festival_floor_and_rating_reasons():
    assert _r(holiday_score=0.5, holiday_event="Republic Day")[0] == dict(code="FESTIVAL", text="Holiday travel: Republic Day")
    assert _r(floor_limited=True)[0]["text"] == "Cost floor of INR 450 limits how low the fare can go"
    assert _r(rival_median=480.0, rating=4.4)[0]["code"] == "RATING"        # high rating, above rivals
    assert _r(rival_median=520.0, rating=3.7)[0]["code"] == "RATING"        # low rating, below rivals
    assert _r(rival_median=480.0, rating=4.0)[0]["code"] == "BOOKING_PACE"  # middling rating: no


def test_at_most_three_reasons_in_priority_order_and_only_fixed_codes():
    got = _r(seats_sold=5.0, band=BAND, rival_median=400.0, holiday_score=1.0, floor_limited=True, rating=4.5)
    assert [g["code"] for g in got] == ["BOOKING_PACE", "RIVAL_GAP", "FESTIVAL"]
    for out in (_run(), _run(rules=_rules(max_change_pct=1.0))):
        assert 1 <= len(out["reasons"]) <= 3 and all(r["code"] in reasons.REASON_CODES for r in out["reasons"])


def test_cost_floor_reason_when_the_floor_is_what_limited_the_fare():
    low = dict(low=400.0, mid=440.0, high=480.0, label="x")  # the model wants a fare below the floor
    out = _run(_svc(fare_on_sale=440.0, average_floor_mid=450.0, predicted_fare=low), seat_fn=flat)
    assert out["suggested_fare"] == 450.0 and "COST_FLOOR" in [r["code"] for r in out["reasons"]]


# ---- API on the real database (same style as the Module A tests) -------------------------------------
def test_api_404_and_422():
    c = TestClient(main.app)
    assert c.get("/services/NOPE/suggestion").status_code == 404
    assert c.get("/services/BKG2023011/suggestion", params={"minutes_since_last_change": -1}).status_code == 422


def test_api_never_breaks_a_rule_and_lists_fixed_reasons_only():
    c = TestClient(main.app)
    rules = c.get("/rules").json()
    for sid in ("BKG2023011", "BKG2023012", "BKG2023013", "BKG2023014", "BKG2023015", "BKG20230120", "BKG20230150"):
        r = c.get(f"/services/{sid}/suggestion")
        if r.status_code == 404:
            continue
        out = r.json()
        assert out["note"] and out["rules_version"] == rules["version"]
        if out["suggested_fare"] is None:
            assert out["blocked_reason"] and out["reasons"] == []
            continue
        f = out["suggested_fare"]
        assert f in rules["fare_steps"] and out["floor_value"] <= f <= rules["ceiling"]
        assert abs(f - out["fare_on_sale"]) <= out["fare_on_sale"] * rules["max_change_pct"] / 100 + 1e-6
        assert 1 <= len(out["reasons"]) <= 3 and all(x["code"] in reasons.REASON_CODES for x in out["reasons"])
        assert out["expected_margin_low"] <= out["expected_margin_mid"] <= out["expected_margin_high"]


def test_at_fare_gives_ordered_ranges_and_no_margin_without_cost():
    got = suggestion.at_fare(dict(low=10.0, mid=12.0, high=15.0), 500.0, 4000.0)
    assert got["revenue"] == dict(low=5000.0, mid=6000.0, high=7500.0)
    assert got["margin"] == dict(low=1000.0, mid=2000.0, high=3500.0)
    assert suggestion.at_fare(dict(low=1.0, mid=2.0, high=3.0), 500.0, None)["margin"] is None


def test_rating_and_nearest_rivals_are_returned_even_when_blocked():
    near = [dict(label="Rival A", minutes_from_ours=-10, fare=480.0), dict(label="Rival B", minutes_from_ours=15, fare=560.0)]
    for svc in (_svc(), _svc(flag_cancelled=True)):
        s = _run(svc=svc, rivals=near)
        assert s["rating"] == dict(avg=4.0, count=500)
        assert s["rivals_either_side"]["before"]["fare"] == 480.0 and s["rivals_either_side"]["after"]["fare"] == 560.0
