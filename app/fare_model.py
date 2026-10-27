"""Step 3: reference fare prediction (Decision Tree). Never the suggested fare.

Served model: the team's own pipeline models/nuego_fare_model.pkl (DecisionTreeRegressor,
depth 5, min leaf 3). Its AC / Sleeper inputs come from the team-supplied file (see
cleaning.attach_coach_attrs); services without them get no prediction. Its competitor
inputs are rebuilt here as-of the booking time, not from the all-time stats the notebook used.
Because that pickle was fit on every row, honest accuracy is measured by refitting the same
architecture on a time-based split (train()); that also gives the low/high range.

Prediction timestamp = booking_time. Competitor rows are used only if captured at or
before it, on the same route, departing within +-3 days. Coach type is NOT a feature: the
NueGo data has no coach type and we do not invent one.
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

PICKLE_PATH = Path(__file__).resolve().parents[1] / "models" / "nuego_fare_model.pkl"
EVAL_PATH = Path(__file__).resolve().parents[1] / "models" / "fare_eval.joblib"
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


def make_model():
    """Same architecture and settings as the team's pickle, for honest evaluation."""
    pre = ColumnTransformer([("categorical", OneHotEncoder(handle_unknown="ignore"),
                              ["Route ID", "AC", "Sleeper"])], remainder="passthrough")
    return make_pipeline(pre, DecisionTreeRegressor(max_depth=5, min_samples_leaf=3, random_state=42))


def train(df: pd.DataFrame, test_frac: float = 0.2) -> dict:
    """Time-based split (oldest -> train, newest -> test) of the team's architecture.

    The metrics are honest out-of-sample numbers; the residual spread gives low/high.
    """
    df = df[~df["flag_cancelled"] & df[NEEDED].notna().all(axis=1)].sort_values("booking_time")
    cut = int(len(df) * (1 - test_frac))
    tr, te = df.iloc[:cut], df.iloc[cut:]
    model = make_model().fit(model_frame(tr), tr["fare_on_sale"])
    pred = model.predict(model_frame(te))
    baseline = te["route_id"].map(tr.groupby("route_id")["fare_on_sale"].median())
    resid = te["fare_on_sale"].to_numpy() - pred
    metrics = dict(n_train=len(tr), n_test=len(te), split_date=str(te["booking_time"].min()),
                   mae_model=float(mean_absolute_error(te["fare_on_sale"], pred)),
                   mae_route_median_baseline=float(mean_absolute_error(te["fare_on_sale"], baseline)))
    # Symmetric range: half-width = 80th percentile of |error| on the held-out (newest) rows.
    # Residual percentiles were not used because newer fares drift above older ones (the
    # held-out errors are mostly positive), which would put "low" above the prediction.
    half = float(np.quantile(np.abs(resid), 0.8))
    metrics["mean_error_bias"] = float(resid.mean())
    return dict(version=MODEL_VERSION, metrics=metrics, resid_low=-half, resid_high=half,
                train_routes={k: int(v) for k, v in df["route_id"].value_counts().items()})


def save(bundle: dict) -> None:
    EVAL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(bundle, EVAL_PATH)


def load() -> dict:
    """The eval bundle plus the team's pickled pipeline under 'model'."""
    return dict(joblib.load(EVAL_PATH), model=joblib.load(PICKLE_PATH))


def predict(bundle: dict, feats: pd.DataFrame) -> pd.DataFrame:
    """Rows missing route/AC/Sleeper get no prediction (NaN) and insufficient_data=True."""
    out = pd.DataFrame(index=feats.index, columns=["fare_low", "fare_mid", "fare_high"], dtype=float)
    ok = feats[NEEDED].notna().all(axis=1)
    if ok.any():
        mid = bundle["model"].predict(model_frame(feats[ok]))
        out.loc[ok, "fare_mid"] = mid.round(0)
        out.loc[ok, "fare_low"] = np.maximum(mid + bundle["resid_low"], 0).round(0)
        out.loc[ok, "fare_high"] = (mid + bundle["resid_high"]).round(0)
    out["insufficient_data"] = (~ok) | (feats["comp_n"] == 0) | (
        feats["route_id"].map(bundle["train_routes"]).fillna(0) < MIN_ROUTE_TRAIN_ROWS)
    out["model_version"] = bundle["version"]
    return out
