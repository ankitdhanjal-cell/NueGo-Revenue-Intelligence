"""Module B: the FIXED list of suggestion reasons. 1 to 3 per suggestion, no free text.

Each reason is a code plus a template with numbers filled in. Add a reason by adding it to
REASON_CODES (which is also the priority order) and to TEMPLATES. Nothing else makes up text.
"""
REASON_CODES = ["BOOKING_PACE", "RIVAL_GAP", "FESTIVAL", "COST_FLOOR", "RATING"]  # priority order
MAX_REASONS = 3
RIVAL_GAP_PCT = 10.0       # suggested fare vs median rival fare
FESTIVAL_SCORE = 0.5       # holiday_score at or above this = holiday or holiday-adjacent
RATING_HIGH, RATING_LOW = 4.3, 3.8

TEMPLATES = {
    "BOOKING_PACE_BEHIND": "{n} seats behind checkpoint",
    "BOOKING_PACE_AHEAD": "{n} seats ahead of checkpoint",
    "BOOKING_PACE_ON": "On pace with similar past services",
    "BOOKING_PACE_NONE": "No checkpoint history yet, pace not assessed",
    "RIVAL_GAP": "Suggested fare is {pct}% {side} the median rival fare (INR {median})",
    "FESTIVAL": "Holiday travel: {event}",
    "COST_FLOOR": "Cost floor of INR {floor} limits how low the fare can go",
    "RATING": "Route rating {avg} from {count} ratings supports a fare {side} rivals",
}


def _pace(sold: float, band: dict | None) -> tuple[str, dict]:
    """behind below p10, ahead above p90, else on pace; no band = no history."""
    if band is None:
        return "BOOKING_PACE_NONE", {}
    if sold < band["p10"]:
        return "BOOKING_PACE_BEHIND", {"n": round(band["p50"] - sold)}
    if sold > band["p90"]:
        return "BOOKING_PACE_AHEAD", {"n": round(sold - band["p50"])}
    return "BOOKING_PACE_ON", {}


def build_reasons(fare: float, seats_sold: float, band: dict | None, rival_median: float | None,
                  holiday_score: float, holiday_event: str, floor_limited: bool, floor: float,
                  rating: float | None, rating_count: int | None) -> list[dict]:
    """Triggered reasons in priority order, at most 3. If none triggered: BOOKING_PACE."""
    key, params = _pace(seats_sold, band)
    found = {}
    if key in ("BOOKING_PACE_BEHIND", "BOOKING_PACE_AHEAD"):
        found["BOOKING_PACE"] = (key, params)
    pct = None if not rival_median else (fare - rival_median) / rival_median * 100
    if pct is not None and abs(pct) > RIVAL_GAP_PCT:
        found["RIVAL_GAP"] = ("RIVAL_GAP", {"pct": round(abs(pct)), "side": "above" if pct > 0 else "below",
                                            "median": round(rival_median)})
    if holiday_score >= FESTIVAL_SCORE:
        found["FESTIVAL"] = ("FESTIVAL", {"event": holiday_event})
    if floor_limited:
        found["COST_FLOOR"] = ("COST_FLOOR", {"floor": round(floor)})
    if pct is not None and rating is not None and ((rating >= RATING_HIGH and pct > 0) or (rating <= RATING_LOW and pct < 0)):
        found["RATING"] = ("RATING", {"avg": round(rating, 1), "count": rating_count,
                                      "side": "above" if pct > 0 else "below"})
    chosen = [c for c in REASON_CODES if c in found][:MAX_REASONS]
    if not chosen:
        found["BOOKING_PACE"] = (key, params)
        chosen = ["BOOKING_PACE"]
    return [{"code": c, "text": TEMPLATES[found[c][0]].format(**found[c][1])} for c in chosen]
