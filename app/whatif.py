"""Module B: what-if table. Every fare step near the current fare with expected seats, revenue and margin.

Seats come from the team seat model, which says more seats at a higher fare in this data, so the seat and
revenue columns are NOT a price-response curve. Each row also says which pricing rule blocks it.
"""
from app.rules import RuleContext, check_fare
from app.suggestion import _f, _times, pick_floor

WINDOW = 0.25  # steps within +-25% of the current fare


def what_if_rows(svc: dict, rule_row: dict, seat_fn, minutes_since_last_change: float | None = None) -> list[dict]:
    """One row per fare step near the current fare. Empty if there is no fare or no seat forecast."""
    current = _f(svc["fare_on_sale"])
    cost = _f(svc["cost_to_run"])
    if current is None:
        return []
    steps = [s for s in rule_row["fare_steps"] if abs(s - current) <= current * WINDOW]
    if not steps:
        return []
    seats = seat_fn(steps)
    if seats is None:
        return []
    floor = pick_floor(svc, rule_row["floor_switch_hours"])["value"]
    nearest = min(steps, key=lambda s: (abs(s - current), s))
    unusable = bool(svc["flag_cancelled"]) or cost is None or floor is None
    ctx = None if unusable else RuleContext(current, floor, rule_row["ceiling"], rule_row["state_cap"],
                                            rule_row["max_change_pct"], rule_row["min_minutes_between_changes"],
                                            minutes_since_last_change, rule_row["fare_steps"])
    rows = []
    for fare in steps:
        revenue = _times(fare, seats[fare])
        rows.append(dict(
            fare=fare, seats=seats[fare], revenue=revenue,
            margin=None if cost is None else {k: v - cost for k, v in revenue.items()},
            blocked_by=["NO_FLOOR"] if ctx is None else check_fare(fare, ctx),
            is_current=fare == nearest, is_suggested=False))
    return rows


def what_if_for_service(engine, service_id: str, minutes_since_last_change: float | None = None) -> dict | None:
    from app.suggestion import load_inputs

    inp = load_inputs(engine, service_id)
    if inp is None:
        return None
    rows = what_if_rows(inp["svc"], inp["rules"], inp["seat_fn"], minutes_since_last_change)
    return {"service_id": service_id, "rows": rows,
            "flags": {"price_response_not_reliable": True, "low_confidence": not rows}}
