"""Train the Linear Regression fare model and save it to models/nuego_fare_model_linear.pkl.

Same data, same inputs and same one-hot step as notebooks/decision_tree.ipynb; only the estimator differs
(one-hot on Route / AC / Sleeper, numbers standardised, LinearRegression). The training rows are the real
services that have a coach type and were not cancelled. Nothing is generated or filled in.

The low / high range is the 80th percentile of 5-fold cross-validated errors, so it comes from services the
model had not seen (unlike the Decision Tree's in-sample range).

Run:  python -m scripts.train_linear_fare_model
"""
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app import fare_model, fare_notebook
from app.db import engine

OUT = fare_model.PICKLE_PATH.with_name("nuego_fare_model_linear.pkl")
NUMERIC = ["Available Seats", "Total Seats", "Distance (km)", "holiday_score", "Departure Month", "Departure Weekday",
           "Departure Hour", "Duration (hours)", "competitor_min_fare", "competitor_median_fare", "competitor_avg_fare"]
CATEGORICAL = ["Route ID", "AC", "Sleeper"]


def new_pipeline():
    pre = ColumnTransformer([("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
                             ("numeric", StandardScaler(), NUMERIC)])
    return make_pipeline(pre, LinearRegression())


def main() -> None:
    feats = fare_notebook.build_features(pd.read_sql_table("services", engine),
                                         pd.read_sql_table("competitor_fares", engine))
    f = feats[~feats["flag_cancelled"] & feats[fare_model.NEEDED].notna().all(axis=1)]
    X, y = fare_model.model_frame(f), f["fare_on_sale"].astype(float)

    cv_pred = cross_val_predict(new_pipeline(), X, y, cv=KFold(5, shuffle=True, random_state=42))
    half_width = float(np.quantile(np.abs(y - cv_pred), 0.8))
    tr, te = train_test_split(np.arange(len(X)), test_size=0.2, random_state=42)  # the notebook's split
    held = new_pipeline().fit(X.iloc[tr], y.iloc[tr]).predict(X.iloc[te])

    model = new_pipeline().fit(X, y)
    meta = dict(model=model, half_width=half_width, rows=len(X),
                cv_mae=float(mean_absolute_error(y, cv_pred)), cv_r2=float(r2_score(y, cv_pred)),
                notebook_split_mae=float(mean_absolute_error(y.iloc[te], held)),
                notebook_split_r2=float(r2_score(y.iloc[te], held)))
    joblib.dump(meta, OUT)
    print(f"saved {OUT.name}: {len(X)} services")
    print(f"  5-fold CV      MAE INR {meta['cv_mae']:.2f}  R2 {meta['cv_r2']:.3f}")
    print(f"  notebook split MAE INR {meta['notebook_split_mae']:.2f}  R2 {meta['notebook_split_r2']:.3f}")
    print(f"  range half-width (80th pct CV error) INR {half_width:.0f}")


if __name__ == "__main__":
    main()
