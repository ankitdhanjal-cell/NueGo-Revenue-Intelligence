import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.cleaning import clean_competitors, clean_services
from scripts.load_raw_csv import FILES, load


def test_raw_files_replace_the_tables_and_repeated_rows_load_once(tmp_path):
    eng = create_engine("sqlite://", poolclass=StaticPool)
    comp = pd.read_csv(FILES["raw_competitor_data"], dtype=str, keep_default_na=False)
    path = tmp_path / "competitors.csv"
    pd.concat([comp.iloc[:30], comp.iloc[:5]]).to_csv(path, index=False)

    assert load(eng, {"raw_competitor_data": path}) == {"raw_competitor_data": 30}
    assert load(eng, {"raw_competitor_data": path}) == {"raw_competitor_data": 30}
    assert len(pd.read_sql_table("raw_competitor_data", eng)) == 30


def test_the_two_raw_files_work_together():
    services = clean_services(pd.read_csv(FILES["raw_route_details"], dtype=str, keep_default_na=False))
    comp = clean_competitors(pd.read_csv(FILES["raw_competitor_data"], dtype=str, keep_default_na=False))
    assert services["route_id"].notna().all() and set(comp["route_id"]) == set(services["route_id"])
    assert comp["fare"].notna().all() and comp["base_fare"].notna().all()
    assert services["holiday_score"].isin([0.0, 0.5, 1.0]).all()
    assert not services["holiday_event"].str.startswith("Original sample row").any()
