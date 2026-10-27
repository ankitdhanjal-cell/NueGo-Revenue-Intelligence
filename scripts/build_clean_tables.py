"""Build the clean `services` table from `raw_route_details`.

Run: python -m scripts.build_clean_tables
"""
import pandas as pd

from app.cleaning import clean_services
from app.db import engine


def main() -> None:
    raw = pd.read_sql_table("raw_route_details", engine)
    services = clean_services(raw)
    services.to_sql("services", engine, if_exists="replace", index=False)
    print(f"services: {len(services)} rows")
    print(services.filter(like="flag_").sum().to_string())


if __name__ == "__main__":
    main()
