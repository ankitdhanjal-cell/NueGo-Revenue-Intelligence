"""Step 4: expected seats sold (the "checkpoint"). Separate from the fare model.

Served model: the team's models/nuego_seats_sold_model.pkl (DecisionTreeRegressor, depth 4,
min leaf 5). It has no days-to-go input, and in this data seats sold barely moves with
days-to-go (correlation ~0.07, one snapshot per service), so we do NOT invent a booking-curve
shape. We return the expected seats sold for the service, with a range, plus the observed
pooled points (real data) for context.
As with the fare model, the pickle was fit on every row, so honest accuracy comes from refitting
the same architecture on a time-based split.
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeRegressor

ROOT = Path(__file__).resolve().parents[1]
PICKLE_PATH = ROOT / "models" / "nuego_seats_sold_model.pkl"
EVAL_PATH = ROOT / "models" / "seat_eval.joblib"
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


def make_model(extra_numeric: bool = False):
    pre = ColumnTransformer([("route", OneHotEncoder(handle_unknown="ignore"), ["Route ID"])],
                            remainder="passthrough")
    return make_pipeline(pre, DecisionTreeRegressor(max_depth=4, min_samples_leaf=5, random_state=42))


def train(df: pd.DataFrame, test_frac: float = 0.2) -> dict:
    """Time-based split of the team's architecture; honest MAE vs the route-mean baseline."""
    df = df[~df["flag_cancelled"] & df[NEEDED].notna().all(axis=1)].sort_values("booking_time")
    cut = int(len(df) * (1 - test_frac))
    tr, te = df.iloc[:cut], df.iloc[cut:]
    pred = make_model().fit(model_frame(tr), tr["seats_sold"]).predict(model_frame(te))
    baseline = te["route_id"].map(tr.groupby("route_id")["seats_sold"].mean())
    resid = te["seats_sold"].to_numpy() - pred
    # does days-to-go help? (same tree with it added) reported, so the "no curve" call is evidence-based
    X1, X2 = model_frame(tr).assign(days_to_go=tr["days_to_go"].to_numpy()), model_frame(te).assign(days_to_go=te["days_to_go"].to_numpy())
    mae_dtg = mean_absolute_error(te["seats_sold"], make_model().fit(X1, tr["seats_sold"]).predict(X2))
    half = float(np.quantile(np.abs(resid), 0.8))
    metrics = dict(n_train=len(tr), n_test=len(te), split_date=str(te["booking_time"].min()),
                   mae_model=float(mean_absolute_error(te["seats_sold"], pred)),
                   mae_route_mean_baseline=float(mean_absolute_error(te["seats_sold"], baseline)),
                   mae_with_days_to_go=float(mae_dtg),
                   corr_seats_vs_days_to_go=float(df["seats_sold"].corr(df["days_to_go"])))
    return dict(version=MODEL_VERSION, metrics=metrics, half_width=half,
                train_routes={k: int(v) for k, v in df["route_id"].value_counts().items()})


def save(bundle: dict) -> None:
    joblib.dump(bundle, EVAL_PATH)


def load() -> dict:
    return dict(joblib.load(EVAL_PATH), model=joblib.load(PICKLE_PATH))


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
