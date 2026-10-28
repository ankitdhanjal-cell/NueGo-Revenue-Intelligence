"""Load the final seats and revenue of departed services into service_outcomes.

CSV columns: service_id, final_seats, final_revenue. Rows for unknown or not-yet-departed services, seats outside
0..total seats, or negative revenue are rejected and listed. Nothing is estimated or filled in.

Run:  python -m scripts.load_outcomes path/to/outcomes.csv
"""
import sys

import pandas as pd

from app import desk, outcomes
from app.db import engine


def main(path: str) -> None:
    rows = pd.read_csv(path, dtype={"service_id": str})
    services = pd.read_sql_table("services", engine, columns=["service_id", "departure_at", "total_seats"])
    good, rejected = outcomes.validate_rows(rows, services, desk.now_ist())
    stored = outcomes.store(engine, good, source=path.rsplit("/", 1)[-1])
    print(f"loaded {stored} outcomes, rejected {len(rejected)}")
    for r in rejected:
        print(f"  {r['service_id']}: {r['reason']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m scripts.load_outcomes path/to/outcomes.csv")
    main(sys.argv[1])
