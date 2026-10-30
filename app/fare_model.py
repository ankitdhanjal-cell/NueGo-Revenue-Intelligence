"""Module B: the predicted fare. A reference for the suggestion, never written to any system.

Linear Regression on the inputs that carry signal in this data:
- route (one-hot), seats still available, holiday score (0 / 0.5 / 1), weekend (Friday to Sunday departure),
- departure year: fares rise every year, in step with costs. Without it the model missed 2026 fares by INR 80.
Left out because they carry no signal here: AC / Sleeper (no fare difference in the data), competitor fares and
distance / duration / total seats (one fixed value per route), month, weekday and hour.

Trained by scripts/train_fare_model.py. The low / high range is the 80th percentile of 5-fold cross-validated
errors (services the model had not seen). A route the model was not trained on gets no prediction.
"""
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

PICKLE_PATH = Path(__file__).resolve().parents[1] / "models" / "nuego_fare_model_linear.pkl"
MODEL_VERSION = "linear regression fare model v2 (route, seats left, holiday, weekend, year)"
NUMERIC = ["available_seats", "holiday_score", "weekend", "year"]
WEEKEND = {4, 5, 6}  # Friday, Saturday, Sunday


def features(df: pd.DataFrame) -> pd.DataFrame:
    """Model inputs from rows with route_id, available_seats, holiday_score and departure_at."""
    dep = pd.to_datetime(df["departure_at"])
    return pd.DataFrame({"route_id": df["route_id"].astype(str), "available_seats": df["available_seats"].astype(float),
                         "holiday_score": df["holiday_score"].astype(float),
                         "weekend": dep.dt.weekday.isin(WEEKEND).astype(int), "year": dep.dt.year}, index=df.index)


def new_pipeline():
    pre = ColumnTransformer([("route", OneHotEncoder(handle_unknown="ignore"), ["route_id"]),
                             ("numeric", StandardScaler(), NUMERIC)])
    return make_pipeline(pre, LinearRegression())


def training_rows(services: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Every service that ran (not cancelled) with a fare on sale."""
    s = services[~services["flag_cancelled"].astype(bool) & services["fare_on_sale"].notna()]
    return features(s), s["fare_on_sale"].astype(float)


@lru_cache(maxsize=1)
def load() -> dict:
    """The saved bundle: model, half_width, routes, rows, cv_mae, cv_r2, future_mae, future_year."""
    return joblib.load(PICKLE_PATH)


def predict(bundle: dict, df: pd.DataFrame) -> pd.DataFrame:
    """fare_low / fare_mid / fare_high per row; NaN with insufficient_data for an unknown route or missing input."""
    x = features(df)
    ok = x["route_id"].isin(bundle["routes"]) & x[NUMERIC].notna().all(axis=1)
    out = pd.DataFrame(index=df.index, columns=["fare_low", "fare_mid", "fare_high"], dtype=float)
    if ok.any():
        mid = np.maximum(bundle["model"].predict(x[ok]), 0)
        out.loc[ok, "fare_mid"] = mid.round(0)
        out.loc[ok, "fare_low"] = np.maximum(mid - bundle["half_width"], 0).round(0)
        out.loc[ok, "fare_high"] = (mid + bundle["half_width"]).round(0)
    out["insufficient_data"] = ~ok
    out["model_version"] = MODEL_VERSION
    return out


def predict_one(service: pd.Series) -> dict | None:
    """One service's prediction as {low, mid, high, model_version}, or None when there is none."""
    p = predict(load(), service.to_frame().T).iloc[0]
    if p["insufficient_data"]:
        return None
    return dict(low=float(p["fare_low"]), mid=float(p["fare_mid"]), high=float(p["fare_high"]),
                model_version=MODEL_VERSION)
