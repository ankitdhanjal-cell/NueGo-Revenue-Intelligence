"""Module B, step 5: suggested fare for one service (FR-PRC-006/007/009). Advice only.

The fare comes from the decision-tree model in notebooks/decision_tree.ipynb (app.fare_notebook).
The suggestion is the allowed fare step CLOSEST to that predicted fare (ties go to the lower step)
among the steps that pass every rule (rules.check_fare): cost floor, ceiling, state cap, largest
change per step, shortest time between changes. So the model sets the price and the rules bound it.

The team seat model gives the expected seats / revenue / margin ranges at the chosen fare. It says
more seats at a higher fare in this data (fare follows demand), so when it is not a reliable price
response (price_response != "used") no gain against the current fare is claimed.
seats_weight is kept in the rules but is not used while the fare comes from the decision tree.
The prediction time is the booking snapshot (services.booking_time).
"""
import numpy as np
import pandas as pd
from sqlalchemy import text

from app import curve as curve_calc
from app import fare_notebook, reasons, rivals, rules
from app.desk_labels import coach_label as _coach
from app.rules import RuleContext, check_fare

NOTE = "Advice only. Nothing is changed or written to any pricing system."


def _f(x, nd=2):
    """NaN / None -> None, else a rounded float."""
    return None if x is None or pd.isna(x) else round(float(x), nd)


def pick_floor(svc: dict, switch_hours: float) -> dict:
    """Which cost floor applies. A missing marginal floor falls back to the average floor (mid), flagged."""
    close = svc["hours_to_departure"] <= switch_hours
    marginal, avg = _f(svc["marginal_floor"]), _f(svc["average_floor_mid"])
    if close and marginal is not None:
        return dict(floor_in_use="marginal", value=marginal, floor_missing=False)
    if close:
        return dict(floor_in_use="average (marginal floor missing, fell back)", value=avg, floor_missing=True)
    return dict(floor_in_use="average", value=avg, floor_missing=False)


def price_response(candidates: list[float], seats: dict) -> str:
    """'used' only if expected seats fall from the lowest to the highest allowed fare."""
    if len(candidates) < 2:
        return "not_assessed"
    return "used" if seats[candidates[-1]]["mid"] < seats[candidates[0]]["mid"] else "not_reliable"


def choose_fare(candidates: list[float], predicted_mid: float) -> float:
    """The allowed fare closest to the model's predicted fare. Ties go to the lower fare."""
    return min(candidates, key=lambda f: (abs(f - predicted_mid), f))


def _times(fare: float, r: dict) -> dict:
    return {k: fare * r[k] for k in ("low", "mid", "high")}


def at_fare(seats: dict, fare: float, cost: float | None) -> dict:
    """Seats, revenue and margin (each low/mid/high) at one fare. Margin is None when the cost is missing."""
    rev = _times(fare, seats)
    return dict(seats=seats, revenue=rev, margin=None if cost is None else {k: v - cost for k, v in rev.items()})


def _minus(a: dict, b: dict) -> dict:
    """Interval difference: wider than the two ranges, so no gain is overstated."""
    return dict(low=a["low"] - b["high"], mid=a["mid"] - b["mid"], high=a["high"] - b["low"])


def _blocked(base: dict, why: str, flags: dict, **extra) -> dict:
    return {**base, "suggested_fare": None, "blocked_reason": why, "reasons": [], "flags": flags, **extra}


def build_suggestion(svc: dict, rule_row: dict, seat_fn, band: dict | None, rival_list: list[dict],
                     minutes_since_last_change: float | None = None) -> dict:
    """The /suggestion response. `seat_fn(fares)` returns {fare: {low, mid, high}} or None (no forecast)."""
    cost, current = _f(svc["cost_to_run"]), _f(svc["fare_on_sale"])
    fl = pick_floor(svc, rule_row["floor_switch_hours"])
    flags = dict(cost_missing=cost is None or svc["margin_status"] == "cost missing", floor_missing=fl["floor_missing"],
                 insufficient_data=False, rival_missing=not rival_list,
                 no_history=svc["checkpoint_status"] != "ok", last_change_unknown=minutes_since_last_change is None)
    base = dict(service_id=svc["service_id"], route_id=svc["route_id"], fare_on_sale=current, engine_fare=current,
                cost_to_run=cost, floor_in_use=fl["floor_in_use"], floor_value=fl["value"],
                floor_switch_hours=rule_row["floor_switch_hours"], hours_to_departure=_f(svc["hours_to_departure"]),
                average_floor_low=_f(svc["average_floor_low"]), average_floor_mid=_f(svc["average_floor_mid"]),
                average_floor_high=_f(svc["average_floor_high"]), marginal_floor=_f(svc["marginal_floor"]),
                checkpoint_status=svc["checkpoint_status"], rules_version=rule_row["version"],
                predicted_fare=svc["predicted_fare"], coach_type=svc.get("coach_type"), note=NOTE)
    if svc["flag_cancelled"]:
        return _blocked(base, "CANCELLED", flags)
    if flags["cost_missing"]:
        return _blocked(base, "COST_MISSING", flags)
    if fl["value"] is None or current is None:
        return _blocked(base, "NO_FLOOR", {**flags, "floor_missing": True})
    if svc["predicted_fare"] is None:
        return _blocked(base, "NO_FARE_PREDICTION", {**flags, "insufficient_data": True})

    ctx = RuleContext(current, fl["value"], rule_row["ceiling"], rule_row["state_cap"], rule_row["max_change_pct"],
                      rule_row["min_minutes_between_changes"], minutes_since_last_change, rule_row["fare_steps"])
    broken = {s: check_fare(s, ctx) for s in ctx.fare_steps}
    candidates = [s for s, v in broken.items() if not v]
    if not candidates:
        counts = pd.Series([c for v in broken.values() for c in v]).value_counts().to_dict()
        ok_without_floor = [s for s, v in broken.items() if not [c for c in v if c != "BELOW_FLOOR"]]
        return _blocked(base, "NO_ALLOWED_FARE", flags, blocked_detail=dict(
            floor_value=fl["value"], highest_fare_allowed_ignoring_floor=max(ok_without_floor, default=None),
            fare_steps_broken_by_rule=counts))

    seats = seat_fn(candidates + [current])
    if seats is None:
        return _blocked(base, "NO_SEAT_FORECAST", {**flags, "insufficient_data": True})
    response = price_response(candidates, seats)
    fare = choose_fare(candidates, svc["predicted_fare"]["mid"])
    chosen = at_fare(seats[fare], fare, cost)
    rev, mar = chosen["revenue"], chosen["margin"]
    floor_limited = any(broken[s] == ["BELOW_FLOOR"] and s < fare for s in broken)
    change = None
    if response == "used":
        change = dict(extra_seats=_minus(seats[fare], seats[current]),
                      margin_change=_minus(mar, at_fare(seats[current], current, cost)["margin"]))
    return {**base, "suggested_fare": fare, "blocked_reason": None,
            "expected_seats": {k: _f(v, 1) for k, v in seats[fare].items()},
            **{f"expected_revenue_{k}": _f(v) for k, v in rev.items()},
            **{f"expected_margin_{k}": _f(v) for k, v in mar.items()},
            "price_response": response, "change_vs_current": change,
            "reasons": reasons.build_reasons(
                fare, svc["seats_sold"], band, svc["rival_median"], svc["holiday_score"], svc["holiday_event"],
                floor_limited, fl["value"], _f(svc["avg_rating"]), svc["num_ratings"]),
            "flags": {**flags, "price_response_not_reliable": response != "used"}}


def seat_fn_for(bundle, service_row: pd.DataFrame):
    """Expected seats (low/mid/high) at any fares for one service, via the team seat model. None if no forecast."""
    from app import seat_model

    def seat_fn(fares: list[float]):
        x = pd.concat([service_row] * len(fares), ignore_index=True)
        x["fare_on_sale"] = fares
        p = seat_model.predict(bundle, x)
        if p["expected_mid"].isna().any():
            return None
        return {f: dict(low=float(r.expected_low), mid=float(r.expected_mid), high=float(r.expected_high))
                for f, r in zip(fares, p.itertuples())}
    return seat_fn


def load_inputs(engine, service_id: str) -> dict | None:
    """Everything build_suggestion needs for one service (a handful of queries). None = unknown service."""
    from app import seat_model

    pnl = pd.read_sql_query(text("SELECT * FROM pnl_services WHERE service_id = :i"), engine, params={"i": service_id})
    if pnl.empty:
        return None
    p = pnl.iloc[0]
    s = pd.read_sql_query(text("SELECT * FROM services WHERE route_id = :r"), engine, params={"r": p["route_id"]},
                          parse_dates=["booking_time", "departure_at"])
    me_row = s[s["service_id"] == service_id]
    me = me_row.iloc[0]
    comp = pd.read_sql_query(text("SELECT operator, departure_at, fare, captured_at, route_id FROM competitor_fares "
                                  "WHERE route_id = :r"), engine, params={"r": p["route_id"]},
                             parse_dates=["departure_at", "captured_at"])
    predicted = fare_notebook.predict_for_service(s, comp, service_id)
    rival_list = rivals.nearby_rivals(me, comp, me["booking_time"])
    median = float(np.median([r["fare"] for r in rival_list])) if rival_list else None
    extras = curve_calc.curve_extras(me_row, s[s["service_id"] != service_id])
    svc = {**p.to_dict(), "seats_sold": me["seats_sold"], "holiday_score": me["holiday_score"],
           "holiday_event": me["holiday_event"], "avg_rating": me["avg_rating"],
           "num_ratings": None if pd.isna(me["num_ratings"]) else int(me["num_ratings"]),
           "rival_median": median,
           "coach_type": _coach(me["ac"], me["sleeper"]),
           "predicted_fare": None if predicted is None else {
               **predicted, "label": "decision-tree prediction (notebooks/decision_tree.ipynb)"}}
    seat_row = seat_model.prepare(s)
    seat_row = seat_row[seat_row["service_id"] == service_id]
    return dict(svc=svc, rules=rules.active_rules(engine), seat_fn=seat_fn_for(seat_model.load(), seat_row),
                band=extras["band"], rivals=rival_list)


def suggest_for_service(engine, service_id: str, minutes_since_last_change: float | None = None) -> dict | None:
    """The suggestion for one service. None = unknown service."""
    inp = load_inputs(engine, service_id)
    if inp is None:
        return None
    return build_suggestion(inp["svc"], inp["rules"], inp["seat_fn"], inp["band"], inp["rivals"],
                            minutes_since_last_change)
