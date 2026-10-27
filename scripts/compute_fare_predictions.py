"""Write reference fare predictions for every service to `fare_predictions`.
Nothing is sent to any external system. Run: python -m scripts.compute_fare_predictions
"""
import pandas as pd

from app import fare_model
from app.db import engine, write_table


def main() -> None:
    feats = fare_model.build_features(pd.read_sql_table("services", engine),
                                      pd.read_sql_table("competitor_fares", engine))
    bundle = fare_model.load()
    pred = fare_model.predict(bundle, feats)
    out = pd.concat([feats[["service_id", "route_id", "ac", "sleeper", "fare_on_sale", "comp_n", "comp_median_fare"]], pred], axis=1)
    out = out.rename(columns={"fare_on_sale": "engine_fare"})
    out["gap_to_engine"] = out["fare_mid"] - out["engine_fare"]
    out["is_reference_only"] = True
    write_table(out, "fare_predictions")
    print(f"fare_predictions: {len(out)} rows, insufficient_data: {int(out['insufficient_data'].sum())}")


if __name__ == "__main__":
    main()
