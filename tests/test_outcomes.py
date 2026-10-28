import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app import decisions, outcomes
from app.decisions import DecisionIn

NOW = pd.Timestamp("2026-10-28 12:00")
SERVICES = pd.DataFrame(dict(service_id=["P1", "P2", "F1"], total_seats=[40, 40, 40],
                             departure_at=pd.to_datetime(["2026-10-01", "2026-10-02", "2026-12-01"])))
USER = dict(id="analyst-1", name="Pricing analyst 1")
SUGGESTION = dict(suggested_fare=520.0, engine_fare=500.0, rules_version=3, floor_value=450.0,
                  predicted_fare=dict(mid=510.0, model_version="linear regression fare model"))


@pytest.fixture()
def eng():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def test_validate_rows_rejects_bad_rows_with_a_reason():
    rows = pd.DataFrame(dict(service_id=["P1", "NOPE", "F1", "P2", "P2"], final_seats=[30, 10, 10, 41, 25],
                             final_revenue=[15000, 100, 100, 100, 12000]))
    good, rejected = outcomes.validate_rows(rows, SERVICES, NOW)
    assert dict(zip(good.service_id, good.final_seats)) == {"P1": 30.0, "P2": 25.0}  # P2's 2nd row replaced the bad 1st one
    assert {r["service_id"]: r["reason"] for r in rejected} == {
        "NOPE": "unknown service", "F1": "service has not departed yet", "P2": "final seats must be between 0 and 40"}
    neg = pd.DataFrame(dict(service_id=["P1"], final_seats=[5], final_revenue=[-1]))
    assert outcomes.validate_rows(neg, SERVICES, NOW)[1][0]["reason"] == "revenue cannot be negative"
    with pytest.raises(ValueError):
        outcomes.validate_rows(pd.DataFrame(dict(service_id=["P1"])), SERVICES, NOW)


def test_a_decision_has_no_outcome_until_one_is_loaded(eng):
    decisions.record_decision(eng, "P1", USER, DecisionIn(action="approve"), SUGGESTION, [520.0])
    assert decisions.list_decisions(eng, "P1")[0]["outcome"] is None
    good, _ = outcomes.validate_rows(pd.DataFrame(dict(service_id=["P1"], final_seats=[31], final_revenue=[16120])), SERVICES, NOW)
    assert outcomes.store(eng, good, "final.csv") == 1
    assert decisions.list_decisions(eng, "P1")[0]["outcome"] == dict(final_seats=31.0, revenue=16120.0)
    good2, _ = outcomes.validate_rows(pd.DataFrame(dict(service_id=["P1"], final_seats=[33], final_revenue=[17000])), SERVICES, NOW)
    outcomes.store(eng, good2, "final2.csv")  # loading again replaces, never duplicates
    assert decisions.list_decisions(eng, "P1")[0]["outcome"]["final_seats"] == 33.0
    assert outcomes.store(eng, good.iloc[0:0], "empty.csv") == 0


def test_decision_records_what_the_suggestion_was_built_from(eng):
    d = decisions.record_decision(eng, "P1", USER, DecisionIn(action="approve"), SUGGESTION, [520.0])
    assert (d["rules_version"], d["model_version"], d["predicted_fare"], d["floor_value"]) == (
        3, "linear regression fare model", 510.0, 450.0)


def test_an_old_decisions_table_gets_the_new_columns_without_losing_rows(eng):
    with eng.begin() as con:
        con.execute(text("CREATE TABLE decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, service_id VARCHAR NOT NULL, "
                         "user_id VARCHAR NOT NULL, user_name VARCHAR NOT NULL, at DATETIME NOT NULL, action VARCHAR NOT NULL, "
                         "fare FLOAT, reason TEXT, category VARCHAR, engine_fare FLOAT, our_fare FLOAT)"))
        con.execute(text("INSERT INTO decisions (service_id, user_id, user_name, at, action, fare) "
                         "VALUES ('OLD', 'admin', 'Admin', '2026-10-01 10:00:00', 'reject', NULL)"))
    rows = decisions.list_decisions(eng, "OLD")
    assert len(rows) == 1 and rows[0]["rules_version"] is None and rows[0]["model_version"] is None
    decisions.record_decision(eng, "NEW", USER, DecisionIn(action="approve"), SUGGESTION, [520.0])
    assert decisions.list_decisions(eng, "NEW")[0]["rules_version"] == 3
