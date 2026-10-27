"""Build the clean `services` table from `raw_route_details`.

Run: python -m scripts.build_clean_tables
"""
import pandas as pd

from pathlib import Path

from app.cleaning import COACH_ATTRS_CSV, attach_coach_attrs, clean_competitors, clean_services
from app.db import engine, write_table


def main() -> None:
    raw = pd.read_sql_table("raw_route_details", engine)
    services = attach_coach_attrs(clean_services(raw), Path(__file__).resolve().parents[1] / COACH_ATTRS_CSV)
    write_table(services, "services")
    comp = clean_competitors(pd.read_sql_table("raw_competitor_data", engine))
    write_table(comp, "competitor_fares")
    print(f"competitor_fares: {len(comp)} rows")
    print(f"services: {len(services)} rows")
    print("services with ac/sleeper:", int(services["ac"].notna().sum()))
    print(services.filter(like="flag_").sum().to_string())


if __name__ == "__main__":
    main()
