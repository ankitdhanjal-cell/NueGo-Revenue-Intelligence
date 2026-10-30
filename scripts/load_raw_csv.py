"""Load the two source CSVs into Postgres as-is (all text), replacing raw_route_details and raw_competitor_data.

The CSVs are the source of truth, so a re-run replaces the tables with the files as they are now. A row that
appears twice in a file is loaded once. Both tables are written in one transaction.
Run: python -m scripts.load_raw_csv   (python -m scripts.refresh runs it first, then rebuilds everything else)
"""
from pathlib import Path

import pandas as pd

from app.db import engine

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "raw_route_details": ROOT / "data/raw/route_details.csv",
    "raw_competitor_data": ROOT / "data/raw/competitor_data.csv",
}


def load(eng, files=FILES) -> dict[str, int]:
    """Rows loaded per table."""
    counts = {}
    with eng.begin() as con:
        for table, path in files.items():
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
            df.columns = [c.strip() for c in df.columns]
            df = df.drop_duplicates()
            df.to_sql(table, con, if_exists="replace", index=False, method="multi", chunksize=500)
            counts[table] = len(df)
    return counts


def main() -> None:
    for table, n in load(engine).items():
        print(f"loaded {table}: {n} rows")


if __name__ == "__main__":
    main()
