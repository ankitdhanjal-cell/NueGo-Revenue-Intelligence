"""Compute service P&L from the clean `services` table into `pnl_services`.
Needs `seat_forecasts` first (run scripts.compute_forecasts).

Run: python -m scripts.compute_pnl
"""
import pandas as pd

from app.db import engine
from app.pnl import add_expected_margin, compute_pnl


def main() -> None:
    services = pd.read_sql_table("services", engine)
    pnl = add_expected_margin(compute_pnl(services), pd.read_sql_table("seat_forecasts", engine))
    pnl.to_sql("pnl_services", engine, if_exists="replace", index=False)
    print(f"pnl_services: {len(pnl)} rows, total profit {pnl['profit'].sum():,.0f}")


if __name__ == "__main__":
    main()
