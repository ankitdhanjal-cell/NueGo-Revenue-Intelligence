"""Load the two source CSVs into Postgres as-is (all text) in raw_* tables.

Safe by design: refuses to touch a table that already exists.
Usage: python scripts/load_raw_csv.py
"""
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

FILES = {
    "raw_route_details": ROOT / "data/raw/route_details.csv",
    "raw_competitor_data": ROOT / "data/raw/competitor_data.csv",
}


def main():
    engine = create_engine(os.environ["DATABASE_URL"])
    existing = set(inspect(engine).get_table_names())
    for table, path in FILES.items():
        if table in existing:
            print(f"skip {table}: already exists")
            continue
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        df.columns = [c.strip() for c in df.columns]
        df.to_sql(table, engine, index=False, method="multi", chunksize=500)
        print(f"loaded {table}: {len(df)} rows, {len(df.columns)} cols")


if __name__ == "__main__":
    main()
