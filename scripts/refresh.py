"""Rebuild everything from the two CSVs, in order, and record the run in `pipeline_runs`:
raw tables, clean tables, fare model, fare predictions, seat forecasts, P&L.

Run:  python -m scripts.refresh   (then restart the API: the fare model is cached)
Daily, for example at 06:00:  0 6 * * *  cd /path/to/repo && .venv/bin/python -m scripts.refresh
"""
from app import pipeline
from app.db import engine
from scripts import (build_clean_tables, compute_fare_predictions, compute_forecasts, compute_pnl, load_raw_csv,
                     train_fare_model)

if __name__ == "__main__":
    pipeline.run(engine, [("raw files", load_raw_csv.main), ("clean tables", build_clean_tables.main),
                          ("fare model", train_fare_model.main), ("fare predictions", compute_fare_predictions.main),
                          ("seat forecasts", compute_forecasts.main), ("profit and loss", compute_pnl.main)])
