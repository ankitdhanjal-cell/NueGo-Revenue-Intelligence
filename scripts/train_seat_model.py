"""Honest time-split evaluation of the seat Decision Tree. Run: python -m scripts.train_seat_model"""
import json

import pandas as pd

from app import seat_model
from app.db import engine


def main() -> None:
    bundle = seat_model.train(seat_model.prepare(pd.read_sql_table("services", engine)))
    seat_model.save(bundle)
    print(json.dumps(bundle["metrics"], indent=2))
    print("range half-width (seats):", round(bundle["half_width"], 1))


if __name__ == "__main__":
    main()
