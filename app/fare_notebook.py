"""Fare prediction exactly as notebooks/decision_tree.ipynb does it (Decision Tree, depth 5, min leaf 3).

The model is models/nuego_fare_model.pkl, trained in that notebook. Its competitor inputs follow the
notebook: min / median / average competitor fare for the route, over ALL competitor rows. The notebook
first groups by route + AC + Sleeper and falls back to the route alone; the competitor file with AC and
Sleeper columns (competitor_preprocessed3.csv) is not in the repo and coach_type_raw is never
interpreted, so only the route-level step is used here. This is NOT restricted to rows captured before a
prediction time (unlike app.fare_model), so for past services it sees later competitor fares.
The low / high range is the 80th percentile of the pickle's own errors on the data (in-sample, optimistic).
Notebook test split: MAE INR 70.87, R2 0.772.
"""
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from app import fare_model

MODEL_VERSION = "decision_tree.ipynb fare model (nuego_fare_model.pkl)"
NOTEBOOK_MAE = 70.87


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
    bundle = fare_model.make_bundle(joblib.load(fare_model.PICKLE_PATH), feats)
    bundle["version"] = MODEL_VERSION
    bundle["range_basis"] = (f"80th percentile of the model's own errors (in-sample, optimistic); "
                             f"notebook test MAE INR {NOTEBOOK_MAE}")
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
