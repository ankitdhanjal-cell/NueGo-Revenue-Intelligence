"""Train the fare model (app.fare_model) on every service that ran, and save it to models/nuego_fare_model_linear.pkl.

Two accuracy checks are saved with it and printed:
- 5-fold cross-validation over all services. Its 80th-percentile error is the low / high range.
- the latest year predicted by a model trained only on the years before it (how it does on dates it has not seen).

Run:  python -m scripts.train_fare_model   (then restart the API: the model is cached)
"""
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict

from app import fare_model
from app.db import engine


def train(services: pd.DataFrame) -> dict:
    X, y = fare_model.training_rows(services)
    cv_pred = cross_val_predict(fare_model.new_pipeline(), X, y, cv=KFold(5, shuffle=True, random_state=42))
    last = int(X["year"].max())
    past, future = X["year"] < last, X["year"] == last
    held = fare_model.new_pipeline().fit(X[past], y[past]).predict(X[future])
    return dict(model=fare_model.new_pipeline().fit(X, y), routes=sorted(X["route_id"].unique()), rows=len(X),
                half_width=float(np.quantile(np.abs(y - cv_pred), 0.8)),
                cv_mae=float(mean_absolute_error(y, cv_pred)), cv_r2=float(r2_score(y, cv_pred)),
                future_year=last, future_mae=float(mean_absolute_error(y[future], held)))


def main() -> None:
    b = train(pd.read_sql_table("services", engine))
    joblib.dump(b, fare_model.PICKLE_PATH)
    print(f"saved {fare_model.PICKLE_PATH.name}: {b['rows']} services, routes {', '.join(b['routes'])}")
    print(f"  5-fold CV: MAE INR {b['cv_mae']:.1f}, R2 {b['cv_r2']:.3f}, range +-INR {b['half_width']:.0f}")
    print(f"  {b['future_year']} predicted from earlier years only: MAE INR {b['future_mae']:.1f}")


if __name__ == "__main__":
    main()
