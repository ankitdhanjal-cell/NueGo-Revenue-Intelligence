"""Step 3: reference fare prediction (Decision Tree). Never the suggested fare.

Served model: the team's own pipeline models/nuego_fare_model.pkl (DecisionTreeRegressor,
depth 5, min leaf 3). Its AC / Sleeper inputs come from the team-supplied file (see
cleaning.attach_coach_attrs); services without them get no prediction. Its competitor
inputs are rebuilt here as-of the booking time, not from the all-time stats the notebook used.
The low/high range comes from that model's own errors on the data (in-sample, so optimistic).

Prediction timestamp = booking_time. Competitor rows are used only if captured at or
before it, on the same route, departing within +-3 days. Coach type is NOT a feature: the
NueGo data has no coach type and we do not invent one.
"""
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

PICKLE_PATH = Path(__file__).resolve().parents[1] / "models" / "nuego_fare_model.pkl"
MODEL_VERSION = "nuego_fare_model.pkl (team Decision Tree v1)"
WINDOW_DAYS = 3
MIN_ROUTE_TRAIN_ROWS = 20

# our column -> the column name the team's pipeline was trained with
COLUMN_MAP = {
    "available_seats": "Available Seats", "total_seats": "Total Seats", "distance_km": "Distance (km)",
    "holiday_score": "holiday_score", "departure_month": "Departure Month",
    "departure_weekday": "Departure Weekday", "departure_hour": "Departure Hour",
    "duration_hours": "Duration (hours)", "comp_min_fare": "competitor_min_fare",
    "comp_median_fare": "competitor_median_fare", "comp_avg_fare": "competitor_avg_fare",
    "route_id": "Route ID", "ac": "AC", "sleeper": "Sleeper"}
NEEDED = ["route_id", "ac", "sleeper"]


def competitor_features(route_id: str, departure_at, as_of, comp: pd.DataFrame) -> dict:
    """Same route, departing within +-3 days, captured at or before `as_of`. Else NaN."""
    c = comp[(comp["route_id"] == route_id) & (comp["captured_at"] <= as_of)
             & ((comp["departure_at"] - departure_at).abs() <= pd.Timedelta(days=WINDOW_DAYS))]
    if c.empty:
        return dict(comp_min_fare=np.nan, comp_median_fare=np.nan, comp_avg_fare=np.nan, comp_n=0)
    return dict(comp_min_fare=c["fare"].min(), comp_median_fare=c["fare"].median(),
                comp_avg_fare=c["fare"].mean(), comp_n=len(c))


def build_features(services: pd.DataFrame, comp: pd.DataFrame) -> pd.DataFrame:
    s = services.copy()
    s.columns = [str(c) for c in s.columns]  # SQL column names are not plain str
    # one scheduled duration per route: fill the few blanks from the same route, never another
    s["duration_hours"] = s["duration_hours"].fillna(s.groupby("route_id")["duration_hours"].transform("median"))
    cf = pd.DataFrame([competitor_features(r.route_id, r.departure_at, r.booking_time, comp)
                       for r in s.itertuples()], index=s.index)
    return pd.concat([s, cf], axis=1)


def model_frame(feats: pd.DataFrame) -> pd.DataFrame:
    return feats[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)


def make_bundle(model, feats: pd.DataFrame) -> dict:
    """The team's pipeline plus a range width taken from its own errors on the data.

    These errors are in-sample (the pickle was fit on this data), so the range is optimistic;
    it is labelled that way in `range_basis`.
    """
    f = feats[~feats["flag_cancelled"] & feats[NEEDED].notna().all(axis=1)]
    err = np.abs(f["fare_on_sale"].to_numpy() - model.predict(model_frame(f)))
    return dict(model=model, version=MODEL_VERSION, half_width=float(np.quantile(err, 0.8)),
                range_basis="80th percentile of the team model's own errors (in-sample, optimistic)",
                train_routes={k: int(v) for k, v in f["route_id"].value_counts().items()})


@lru_cache(maxsize=1)
def load() -> dict:
    from app.db import engine  # imported here so the module works without a database in tests
    feats = build_features(pd.read_sql_table("services", engine), pd.read_sql_table("competitor_fares", engine))
    return make_bundle(joblib.load(PICKLE_PATH), feats)


def predict(bundle: dict, feats: pd.DataFrame) -> pd.DataFrame:
    """Rows missing route/AC/Sleeper get no prediction (NaN) and insufficient_data=True."""
    out = pd.DataFrame(index=feats.index, columns=["fare_low", "fare_mid", "fare_high"], dtype=float)
    ok = feats[NEEDED].notna().all(axis=1)
    if ok.any():
        mid = bundle["model"].predict(model_frame(feats[ok]))
        out.loc[ok, "fare_mid"] = mid.round(0)
        out.loc[ok, "fare_low"] = np.maximum(mid - bundle["half_width"], 0).round(0)
        out.loc[ok, "fare_high"] = (mid + bundle["half_width"]).round(0)
    out["insufficient_data"] = (~ok) | (feats["comp_n"] == 0) | (
        feats["route_id"].map(bundle["train_routes"]).fillna(0) < MIN_ROUTE_TRAIN_ROWS)
    out["model_version"] = bundle["version"]
    return out
