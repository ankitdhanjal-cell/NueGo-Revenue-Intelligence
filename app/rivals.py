"""Module B, step 2: competitor departures near one of our services, with operator names.

Two lists, both on our route only and never including NueGo's own rows in the competitor file:
- rivals: departing within +-30 minutes, latest fare captured at or before the prediction time (our booking
  snapshot; a later capture would be hindsight). Only these feed the RIVAL_GAP and RATING reasons.
- nearby fares: departing within +-3 days, to compare prices. Each departure's latest capture, marked when it
  was captured after the prediction time.
"""
import pandas as pd

WINDOW_MINUTES = 30
NEARBY_DAYS = 3
OWN_OPERATOR = "nuego"


def _competitors(service: pd.Series, comp: pd.DataFrame) -> pd.DataFrame:
    """Other operators' rows on our route."""
    return comp[(comp["route_id"] == service["route_id"]) & (comp["operator"].str.casefold() != OWN_OPERATOR)]


def _latest(c: pd.DataFrame) -> pd.DataFrame:
    """One row per competitor departure (operator + departure time), its latest capture, in departure order."""
    return (c.sort_values("captured_at").groupby(["operator", "departure_at"], as_index=False).last()
            .sort_values(["departure_at", "operator"]))


def _fare_row(r, service: pd.Series) -> dict:
    ours = service["fare_on_sale"]
    return dict(operator=r.operator, departure_at=str(r.departure_at),
                minutes_from_ours=int((r.departure_at - service["departure_at"]).total_seconds() // 60),
                fare=float(r.fare), gap_to_ours=None if pd.isna(ours) else float(ours - r.fare),
                captured_at=str(r.captured_at))


def nearby_rivals(service: pd.Series, comp: pd.DataFrame, as_of) -> list[dict]:
    """Competitor departures within +-30 minutes, latest capture <= as_of. [] when there are none: never made up."""
    c = _competitors(service, comp)
    c = c[((c["departure_at"] - service["departure_at"]).abs() <= pd.Timedelta(minutes=WINDOW_MINUTES))
          & (c["captured_at"] <= as_of)]
    return [_fare_row(r, service) for r in _latest(c).itertuples()]


def nearby_fares(service: pd.Series, comp: pd.DataFrame, as_of) -> list[dict]:
    """Competitor departures within +-3 days, each with its latest capture, flagged if captured after as_of."""
    c = _competitors(service, comp)
    c = c[(c["departure_at"] - service["departure_at"]).abs() <= pd.Timedelta(days=NEARBY_DAYS)]
    return [{**_fare_row(r, service), "captured_after_prediction_time": bool(r.captured_at > as_of)}
            for r in _latest(c).itertuples()]


def either_side(rivals: list[dict]) -> dict:
    """The nearest rival departing before ours and the nearest at or after ours (None when there is none)."""
    before = [r for r in rivals if r["minutes_from_ours"] < 0]
    after = [r for r in rivals if r["minutes_from_ours"] >= 0]
    return dict(before=max(before, key=lambda r: r["minutes_from_ours"], default=None),
                after=min(after, key=lambda r: r["minutes_from_ours"], default=None))


def _duration(minutes: int) -> str:
    days, rest = divmod(minutes, 24 * 60)
    hours, mins = divmod(rest, 60)
    return " ".join(f"{v} {u}" for v, u in ((days, "d"), (hours, "h"), (mins, "min")) if v) or "0 min"


def why_missing(service: pd.Series, comp: pd.DataFrame, as_of) -> tuple[str, str]:
    """(code, sentence) saying why no rival is shown for this service."""
    later = nearby_rivals(service, comp, pd.Timestamp.max)
    if later:
        return ("captured_after_prediction_time",
                f"{len(later)} rival departure(s) within 30 minutes, but every fare was captured after the "
                f"prediction time ({as_of:%d %b %Y %H:%M}), so none is used. Nothing is estimated.")
    same = _competitors(service, comp)
    if same.empty:
        return "no_route_data", "There is no competitor data for this route. Nothing is estimated."
    nearest = int((same["departure_at"] - service["departure_at"]).abs().min().total_seconds() // 60)
    return ("none_within_30_minutes",
            f"No rival departs within 30 minutes of ours. The nearest rival departure on this route is "
            f"{_duration(nearest)} away. Nothing is estimated.")


def rival_view(service: pd.Series, comp: pd.DataFrame, as_of) -> dict:
    """The /rivals response. Our rating comes from the services table (route rating)."""
    rivals = nearby_rivals(service, comp, as_of)
    rating = None if pd.isna(service["avg_rating"]) else float(service["avg_rating"])
    count = None if pd.isna(service["num_ratings"]) else int(service["num_ratings"])
    missing_reason, note = ((None, "Only fares captured at or before the prediction time are used in the reasons.")
                            if rivals else why_missing(service, comp, as_of))
    return {
        "service_id": service["service_id"], "route_id": service["route_id"],
        "as_of": str(as_of), "our_departure_at": str(service["departure_at"]),
        "our_fare_on_sale": None if pd.isna(service["fare_on_sale"]) else float(service["fare_on_sale"]),
        "window_minutes": WINDOW_MINUTES, "rival_count": len(rivals), "rivals": rivals,
        "nearby_days": NEARBY_DAYS, "nearby_fares": nearby_fares(service, comp, as_of),
        "route_rating": {"avg": rating, "count": count},
        "flags": {"rival_missing": not rivals},
        "missing_reason": missing_reason, "note": note,
    }
