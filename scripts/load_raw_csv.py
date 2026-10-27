"""Load the two source CSVs into Postgres as-is (all text) in raw_* tables.

Safe by design: skips a table that already has rows. Tables come from `alembic upgrade head`.
Usage: python scripts/load_raw_csv.py
"""
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

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
        if table not in existing:
            raise SystemExit(f"table {table} does not exist: run `alembic upgrade head` first")
        with engine.connect() as conn:
            if conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar():
                print(f"skip {table}: already has rows")
                continue
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        df.columns = [c.strip() for c in df.columns]
        df.to_sql(table, engine, if_exists="append", index=False, method="multi", chunksize=500)
        print(f"loaded {table}: {len(df)} rows, {len(df.columns)} cols")


if __name__ == "__main__":
    main()
