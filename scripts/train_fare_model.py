"""Train the fare Decision Tree. Run: python -m scripts.train_fare_model"""
import json

import pandas as pd

from app import fare_model
from app.db import engine


def main() -> None:
    feats = fare_model.build_features(pd.read_sql_table("services", engine),
                                      pd.read_sql_table("competitor_fares", engine))
    bundle = fare_model.train(feats)
    fare_model.save(bundle)
    print(json.dumps(bundle["metrics"], indent=2))
    print("range residuals (p10, p90):", round(bundle["resid_low"], 1), round(bundle["resid_high"], 1))
    print("services with a competitor match:", int((feats["comp_n"] > 0).sum()), "of", len(feats))


if __name__ == "__main__":
    main()
