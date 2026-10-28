"""Module B, step 2: rival departures near one of our services, anonymised.

Rival rows are used only if captured at or before the prediction time (same as-of rule as
fare_model.competitor_features). Operator names are read from the database but never returned:
rivals are labelled "Rival A", "Rival B", ... in departure-time order.
"""
import pandas as pd

WINDOW_MINUTES = 30


def rival_label(i: int) -> str:
    """0 -> 'Rival A', 25 -> 'Rival Z', 26 -> 'Rival AA'."""
    name = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        name = chr(65 + r) + name
    return f"Rival {name}"


def nearby_rivals(service: pd.Series, comp: pd.DataFrame, as_of) -> list[dict]:
    """Rival departures on the same route within +-30 minutes, latest capture <= as_of.

    One entry per rival departure (operator + departure time); a later capture replaces an
    earlier one. Returns [] when there are none: never a made-up rival.
    """
    gap = (comp["departure_at"] - service["departure_at"]).abs()
    c = comp[(comp["route_id"] == service["route_id"]) & (gap <= pd.Timedelta(minutes=WINDOW_MINUTES))
             & (comp["captured_at"] <= as_of)]
    c = (c.sort_values("captured_at").groupby(["operator", "departure_at"], as_index=False).last()
         .sort_values(["departure_at", "operator"]).reset_index(drop=True))
    ours = service["fare_on_sale"]
    return [dict(label=rival_label(i), departure_at=str(r.departure_at),
                 minutes_from_ours=int((r.departure_at - service["departure_at"]).total_seconds() // 60),
                 fare=float(r.fare), gap_to_ours=None if pd.isna(ours) else float(ours - r.fare),
                 captured_at=str(r.captured_at))
            for i, r in enumerate(c.itertuples())]


def rival_view(service: pd.Series, comp: pd.DataFrame, as_of) -> dict:
    """The /rivals response. Our rating comes from the services table (route rating)."""
    rivals = nearby_rivals(service, comp, as_of)
    rating = None if pd.isna(service["avg_rating"]) else float(service["avg_rating"])
    count = None if pd.isna(service["num_ratings"]) else int(service["num_ratings"])
    return {
        "service_id": service["service_id"], "route_id": service["route_id"],
        "as_of": str(as_of), "our_departure_at": str(service["departure_at"]),
        "our_fare_on_sale": None if pd.isna(service["fare_on_sale"]) else float(service["fare_on_sale"]),
        "window_minutes": WINDOW_MINUTES, "rival_count": len(rivals), "rivals": rivals,
        "route_rating": {"avg": rating, "count": count},
        "flags": {"rival_missing": not rivals},
        "note": ("No rival fare captured at or before the prediction time within 30 minutes. "
                 "Nothing is estimated." if not rivals else
                 "Rivals are anonymised. Only fares captured at or before the prediction time are shown."),
    }
