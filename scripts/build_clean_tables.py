"""Build the clean `services` table from `raw_route_details`.

Run: python -m scripts.build_clean_tables
"""
import pandas as pd

from pathlib import Path

from app.cleaning import COACH_ATTRS_CSV, attach_coach_attrs, clean_competitors, clean_services
from app.db import engine


def main() -> None:
    raw = pd.read_sql_table("raw_route_details", engine)
    services = attach_coach_attrs(clean_services(raw), Path(__file__).resolve().parents[1] / COACH_ATTRS_CSV)
    services.to_sql("services", engine, if_exists="replace", index=False)
    comp = clean_competitors(pd.read_sql_table("raw_competitor_data", engine))
    comp.to_sql("competitor_fares", engine, if_exists="replace", index=False)
    print(f"competitor_fares: {len(comp)} rows")
    print(f"services: {len(services)} rows")
    print("services with ac/sleeper:", int(services["ac"].notna().sum()))
    print(services.filter(like="flag_").sum().to_string())


if __name__ == "__main__":
    main()
