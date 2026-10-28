"""Fare prediction: Linear Regression on the same inputs as notebooks/decision_tree.ipynb.

The served model is models/nuego_fare_model_linear.pkl, made by scripts/train_linear_fare_model.py (one-hot
Route / AC / Sleeper, standardised numbers, LinearRegression). It beat the notebook's Decision Tree on every
split we tried (notebook split: MAE INR ~41 against 70.87). The Decision Tree pickle is kept in models/.

Competitor inputs follow the notebook: min / median / average competitor fare for the route, over ALL
competitor rows. The notebook first groups by route + AC + Sleeper and falls back to the route alone; the
competitor file with AC and Sleeper columns (competitor_preprocessed3.csv) is not in the repo, so only the
route-level step is used. This is NOT restricted to rows captured before a prediction time (unlike
app.fare_model), so for past services it sees later competitor fares.
The low / high range is the 80th percentile of 5-fold cross-validated errors (services the model had not seen).
No coach type (AC / Sleeper) means no prediction.
"""
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from app import fare_model

MODEL_VERSION = "linear regression fare model (nuego_fare_model_linear.pkl)"
LINEAR_PICKLE_PATH = fare_model.PICKLE_PATH.with_name("nuego_fare_model_linear.pkl")


def route_stats(comp: pd.DataFrame) -> pd.DataFrame:
    """Notebook level 2: competitor fare min / median / mean per route (all rows)."""
    g = comp.groupby("route_id")["fare"].agg(comp_min_fare="min", comp_median_fare="median",
                                             comp_avg_fare="mean", comp_n="count")
    return g.reset_index()


def build_features(services: pd.DataFrame, comp: pd.DataFrame) -> pd.DataFrame:
    s = services.copy()
    s.columns = [str(c) for c in s.columns]
    s["duration_hours"] = s["duration_hours"].fillna(s.groupby("route_id")["duration_hours"].transform("median"))
    s = s.drop(columns=[c for c in ("comp_min_fare", "comp_median_fare", "comp_avg_fare", "comp_n") if c in s])
    out = s.merge(route_stats(comp), on="route_id", how="left")
    out["comp_n"] = out["comp_n"].fillna(0)
    return out


@lru_cache(maxsize=1)
def load() -> dict:
    from app.db import engine  # imported here so the module works without a database in tests
    feats = build_features(pd.read_sql_table("services", engine), pd.read_sql_table("competitor_fares", engine))
    saved = joblib.load(LINEAR_PICKLE_PATH)
    bundle = fare_model.make_bundle(saved["model"], feats)
    bundle["version"] = MODEL_VERSION
    bundle["half_width"] = saved["half_width"]
    bundle["range_basis"] = (f"80th percentile of 5-fold cross-validated errors on {saved['rows']} services; "
                             f"cross-validated MAE INR {saved['cv_mae']:.0f}")
    return bundle


def predict(bundle: dict, feats: pd.DataFrame) -> pd.DataFrame:
    """fare_low / fare_mid / fare_high per row. No coach type (AC / Sleeper) means no prediction, never a guess."""
    return fare_model.predict(bundle, feats)


def predict_for_service(services_of_route: pd.DataFrame, comp: pd.DataFrame, service_id: str) -> dict | None:
    """One service's prediction as {low, mid, high, model_version, insufficient_data}, or None if unavailable."""
    feats = build_features(services_of_route, comp)
    row = feats[feats["service_id"] == service_id]
    if row.empty:
        return None
    p = predict(load(), row).iloc[0]
    if pd.isna(p["fare_mid"]):
        return None
    return dict(low=float(p["fare_low"]), mid=float(p["fare_mid"]), high=float(p["fare_high"]),
                model_version=str(p["model_version"]), insufficient_data=bool(p["insufficient_data"]),
                competitor_rows_used=int(np.nan_to_num(row["comp_n"].iloc[0])))
