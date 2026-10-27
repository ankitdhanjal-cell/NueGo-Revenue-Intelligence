"""Step 2: Module A, service P&L. Plain arithmetic, no ML.

cost_to_run = distance_km x coach_cost_per_km + crew_cost_split + tolls
  crew_cost is a route-level MONTHLY figure, so (per the brief) it is split across the
  month's trips by scheduled hours:
      crew_cost_split = monthly_crew x trip_hours / (trips_per_month x route_avg_hours)
  The monthly route cost itself is repeated on every row and is NOT added again.
revenue     = seats_sold x fare_on_sale, minus refund_amount if cancelled (floor 0)
"""
import numpy as np
import pandas as pd

from app.config import FLOOR_SWITCH_HOURS, MIN_HISTORY_DAYS, TRIPS_PER_ROUTE_MONTH


def split_crew(s: pd.DataFrame, trips_per_month: int) -> pd.DataFrame:
    """Per-trip crew cost from the monthly crew total, split by scheduled hours.

    A missing duration is taken from the same route's other trips (a route has one
    scheduled duration) and flagged, never guessed from another route.
    """
    route_hours = s.groupby("route_id")["duration_hours"].transform("median")
    hours = s["duration_hours"].fillna(route_hours)
    share = hours / (trips_per_month * route_hours)
    return pd.DataFrame({"crew_cost_split": s["crew_cost"] * share,
                         "flag_duration_from_route": s["duration_hours"].isna()})


def compute_pnl(services: pd.DataFrame, trips_per_month: int = TRIPS_PER_ROUTE_MONTH) -> pd.DataFrame:
    s = services.copy()
    if "duration_hours" not in s:
        s["duration_hours"] = float("nan")
    crew = split_crew(s, trips_per_month)
    out = pd.DataFrame({
        "service_id": s["service_id"],
        "route_id": s["route_id"],
        "corridor": s["origin"] + " - " + s["destination"],
        "departure_at": s["departure_at"],
        "departure_date": s["departure_at"].dt.date.astype(str),
        "booking_status": s["booking_status"],
        "seats_sold": s["seats_sold"],
        "total_seats": s["total_seats"],
        "fare_on_sale": s["fare_on_sale"],
    })
    gross = s["seats_sold"] * s["fare_on_sale"]
    refund = np.where(s["flag_cancelled"], s["refund_amount"], 0)
    out["gross_revenue"] = gross
    out["refund"] = refund
    out["revenue"] = (gross - refund).clip(lower=0)

    out["crew_cost_split"] = crew["crew_cost_split"]
    out["cost_to_run"] = (s["distance_km"] * s["coach_cost_per_km"]
                          + out["crew_cost_split"] + s["tolls"])
    out["flag_crew_split_assumed"] = True  # trips per month is a setting, not data
    out["flag_duration_from_route"] = crew["flag_duration_from_route"]
    out["profit"] = out["revenue"] - out["cost_to_run"]
    out["margin_pct"] = np.where(out["revenue"] > 0, out["profit"] / out["revenue"] * 100, np.nan)

    # Floor 1: fare at which the seats sold so far cover the cost to run.
    out["breakeven_fare_current_seats"] = np.where(
        out["seats_sold"] > 0, out["cost_to_run"] / out["seats_sold"], np.nan)
    # Floor 2: fare at which a full coach covers the cost to run.
    out["breakeven_fare_full_coach"] = out["cost_to_run"] / out["total_seats"]
    # Marginal floor needs channel commission, which is not in the data.
    out["marginal_floor"] = np.nan
    out["marginal_floor_note"] = "cost missing: no channel commission data"

    out["margin_status"] = np.where(out["cost_to_run"].isna(), "cost missing", "ok")
    first = s.groupby("route_id")["departure_at"].transform("min")
    out["route_history_days"] = (s["departure_at"] - first).dt.days
    out["checkpoint_status"] = np.where(out["route_history_days"] >= MIN_HISTORY_DAYS, "ok", "no history")
    out["hours_to_departure"] = (s["days_to_go"] * 24) if "days_to_go" in s else np.nan
    out["flag_cancelled"] = s["flag_cancelled"]
    out["flag_revenue_is_estimate"] = True  # seats_sold is a booking-time snapshot
    return out


def add_expected_margin(pnl: pd.DataFrame, forecasts: pd.DataFrame) -> pd.DataFrame:
    """Expected margin = predicted final revenue - cost to run, as low / mid / high.

    Predicted revenue = expected seats sold (seat forecast) x the fare on sale. The brief
    takes it from Module B; Module B does not exist yet, so the seat forecast stands in and
    is labelled so. No forecast or no cost -> NaN, never a filled-in number.
    """
    f = forecasts.set_index("service_id")
    out = pnl.copy()
    for k in ("low", "mid", "high"):
        seats = out["service_id"].map(f[f"expected_{k}"])
        out[f"expected_revenue_{k}"] = seats * out["fare_on_sale"]
        out[f"expected_margin_{k}"] = out[f"expected_revenue_{k}"] - out["cost_to_run"]
    # Average floor (brief): cost to run / EXPECTED seats sold. Range: more seats -> lower floor.
    cost = out["cost_to_run"]
    for k, src in (("low", "high"), ("mid", "mid"), ("high", "low")):
        seats = out["service_id"].map(f[f"expected_{src}"]).where(lambda x: x > 0)
        out[f"average_floor_{k}"] = cost / seats
    # Which floor applies is recorded on the row, with the switch point that was used.
    out["floor_switch_hours"] = FLOOR_SWITCH_HOURS
    close = out["hours_to_departure"] <= FLOOR_SWITCH_HOURS
    out["floor_in_use"] = np.where(close, "marginal (cost missing)", "average")
    out["expected_margin_source"] = "seat forecast x fare on sale (stand-in for Module B)"
    out["forecast_insufficient_data"] = out["service_id"].map(f["insufficient_data"]).fillna(True).astype(bool)
    return out


# Dimensions Module A can group by. coach_type and channel are not in the data.
GROUPABLE = {"corridor": "corridor", "date": "departure_date"}
UNAVAILABLE = {"coach_type", "channel"}


def totals(pnl: pd.DataFrame, group_by: str) -> pd.DataFrame:
    pnl = pnl[~pnl["flag_cancelled"]]  # cancelled services are listed separately
    g = pnl.groupby(GROUPABLE[group_by]).agg(
        services=("service_id", "count"),
        revenue=("revenue", "sum"),
        cost_to_run=("cost_to_run", "sum"),
        profit=("profit", "sum"),
    ).reset_index().rename(columns={GROUPABLE[group_by]: group_by})
    g["margin_pct"] = np.where(g["revenue"] > 0, g["profit"] / g["revenue"] * 100, np.nan)
    return g


def rank(pnl: pd.DataFrame, forecasts: pd.DataFrame, w_behind: float, w_margin: float):
    """Attention ranking (FR-PNL-005). Returns (ranked, excluded).

    behind_part = seats below the expected (mid) checkpoint / total seats
    margin_part = expected loss at the mid forecast / cost to run, capped at 1
    Highest score first; ties go to the earliest departure, then service_id, so the same data
    always gives the same order. Cancelled, cost-missing and no-forecast services are excluded.
    """
    df = pnl.merge(forecasts[["service_id", "expected_mid"]], on="service_id", how="left")
    reason = np.select(
        [df["flag_cancelled"], df["margin_status"] == "cost missing", df["expected_mid"].isna()],
        ["cancelled", "cost missing", "no forecast"], default="")
    df["excluded_reason"] = reason
    ok = df[df["excluded_reason"] == ""].copy()
    ok["behind_part"] = (ok["expected_mid"] - ok["seats_sold"]).clip(lower=0) / ok["total_seats"]
    ok.loc[ok["checkpoint_status"] != "ok", "behind_part"] = 0.0  # "no history": no checkpoint to be behind
    ok["margin_part"] = (-ok["expected_margin_mid"]).clip(lower=0) / ok["cost_to_run"]
    ok["margin_part"] = ok["margin_part"].clip(upper=1)
    ok["score"] = w_behind * ok["behind_part"] + w_margin * ok["margin_part"]
    ranked = ok.sort_values(["score", "departure_at", "service_id"], ascending=[False, True, True])
    ranked.insert(0, "rank", range(1, len(ranked) + 1))
    cols = ["rank", "service_id", "route_id", "departure_at", "score", "behind_part", "margin_part",
            "checkpoint_status", "seats_sold", "expected_mid", "expected_margin_mid"]
    return ranked[cols], df.loc[df["excluded_reason"] != "", ["service_id", "excluded_reason"]]


HISTORY_DAYS = 56  # 8 weeks


def trend(pnl: pd.DataFrame, service_id: str) -> dict:
    """Same route, same weekday, previous 8 weeks (FR-PNL-006)."""
    me = pnl[pnl["service_id"] == service_id].iloc[0]
    route = pnl[(pnl["route_id"] == me["route_id"]) & ~pnl["flag_cancelled"]]
    start = me["departure_at"] - pd.Timedelta(days=HISTORY_DAYS)
    past = route[(route["departure_at"] < me["departure_at"]) & (route["departure_at"] >= start)
                 & (route["departure_at"].dt.day_of_week == me["departure_at"].weekday())]
    history_days = (me["departure_at"] - route["departure_at"].min()).days
    return {
        "service_id": service_id, "weekday": me["departure_at"].day_name(),
        "window": f"{start.date()} to {me['departure_at'].date()}",
        "services_found": len(past),
        "history_days_for_route": history_days,
        "checkpoint_status": "ok" if history_days >= MIN_HISTORY_DAYS else "no history",
        "trend_available": len(past) > 0,
        "points": [dict(departure_at=str(r.departure_at), load_pct=round(r.seats_sold / r.total_seats * 100, 1),
                        revenue=float(r.revenue), margin=None if pd.isna(r.profit) else float(r.profit))
                   for r in past.sort_values("departure_at").itertuples()],
    }
