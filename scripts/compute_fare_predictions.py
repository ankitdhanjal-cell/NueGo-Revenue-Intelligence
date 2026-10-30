"""Write the predicted fare for every service to `fare_predictions` (read by GET /services/{id}/fare-prediction).
Nothing is sent to any external system. Run: python -m scripts.compute_fare_predictions
"""
import pandas as pd

from app import fare_model
from app.db import engine


def main() -> None:
    s = pd.read_sql_table("services", engine)
    s.columns = [str(c) for c in s.columns]
    pred = fare_model.predict(fare_model.load(), s)
    out = pd.concat([s[["service_id", "route_id"]], s["fare_on_sale"].rename("engine_fare"), pred], axis=1)
    out["gap_to_engine"] = out["fare_mid"] - out["engine_fare"]
    out.to_sql("fare_predictions", engine, if_exists="replace", index=False)
    print(f"fare_predictions: {len(out)} rows, no prediction: {int(out['insufficient_data'].sum())}")


if __name__ == "__main__":
    main()
