"""Step 4: expected seats sold (the "checkpoint"). Separate from the fare model.

Served model: the team's models/nuego_seats_sold_model.pkl (DecisionTreeRegressor, depth 4,
min leaf 5). It has no days-to-go input, and in this data seats sold barely moves with
days-to-go (correlation ~0.07, one snapshot per service), so we do NOT invent a booking-curve
shape. We return the expected seats sold for the service, with a range, plus the observed
pooled points (real data) for context.
The low/high range comes from the model's own errors on the data (in-sample, so optimistic).
"""
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PICKLE_PATH = ROOT / "models" / "nuego_seats_sold_model.pkl"
MODEL_VERSION = "nuego_seats_sold_model.pkl (team Decision Tree v1)"
MIN_ROUTE_TRAIN_ROWS = 20

COLUMN_MAP = {
    "total_seats": "Total Seats", "distance_km": "Distance (km)", "holiday_score": "holiday_score",
    "departure_month": "Departure Month", "departure_weekday": "Departure Weekday",
    "departure_hour": "Departure Hour", "duration_hours": "Duration (hours)",
    "fare_on_sale": "Fare on Sale (INR)", "ac": "AC", "sleeper": "Sleeper", "route_id": "Route ID"}
NEEDED = ["route_id", "ac", "sleeper"]


def prepare(services: pd.DataFrame) -> pd.DataFrame:
    s = services.copy()
    s.columns = [str(c) for c in s.columns]
    s["duration_hours"] = s["duration_hours"].fillna(s.groupby("route_id")["duration_hours"].transform("median"))
    return s


def model_frame(s: pd.DataFrame) -> pd.DataFrame:
    return s[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)


def make_bundle(model, s: pd.DataFrame) -> dict:
    """The team's pipeline plus a range width from its own errors (in-sample, optimistic)."""
    f = s[~s["flag_cancelled"] & s[NEEDED].notna().all(axis=1)]
    err = np.abs(f["seats_sold"].to_numpy() - model.predict(model_frame(f)))
    return dict(model=model, version=MODEL_VERSION, half_width=float(np.quantile(err, 0.8)),
                range_basis="80th percentile of the team model's own errors (in-sample, optimistic)",
                train_routes={k: int(v) for k, v in f["route_id"].value_counts().items()})


@lru_cache(maxsize=1)
def load() -> dict:
    from app.db import engine
    return make_bundle(joblib.load(PICKLE_PATH), prepare(pd.read_sql_table("services", engine)))


def predict(bundle: dict, s: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=s.index, columns=["expected_low", "expected_mid", "expected_high"], dtype=float)
    ok = s[NEEDED].notna().all(axis=1)
    if ok.any():
        mid = np.clip(bundle["model"].predict(model_frame(s[ok])), 0, s.loc[ok, "total_seats"])
        out.loc[ok, "expected_mid"] = mid.round(1)
        out.loc[ok, "expected_low"] = np.clip(mid - bundle["half_width"], 0, None).round(1)
        out.loc[ok, "expected_high"] = np.minimum(mid + bundle["half_width"], s.loc[ok, "total_seats"]).round(1)
    out["insufficient_data"] = (~ok) | (s["route_id"].map(bundle["train_routes"]).fillna(0) < MIN_ROUTE_TRAIN_ROWS)
    out["model_version"] = bundle["version"]
    return out
