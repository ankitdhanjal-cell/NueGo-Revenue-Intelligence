"""Refresh the computed tables in order (seat forecasts, then P&L) and record the run in `pipeline_runs`.

Run:  python -m scripts.refresh
Daily, for example at 06:00:  0 6 * * *  cd /path/to/repo && .venv/bin/python -m scripts.refresh
"""
from app import pipeline
from app.db import engine
from scripts import compute_forecasts, compute_pnl

if __name__ == "__main__":
    pipeline.run(engine, [("seat forecasts", compute_forecasts.main), ("profit and loss", compute_pnl.main)])
