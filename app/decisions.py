"""Module B: decisions. A person approves, changes or rejects a suggestion; it is only RECORDED here.
Nothing is ever sent to the pricing engine or any other system.
"""
from datetime import datetime
from typing import Literal

import pandas as pd

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Float, Integer, MetaData, String, Table, Text, insert, inspect, select, text

from app import outcomes as outcomes_calc
from app.suggestion import build_suggestion, load_inputs
from app.whatif import what_if_rows

metadata = MetaData()
decisions = Table(
    "decisions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("service_id", String, nullable=False, index=True),
    Column("user_id", String, nullable=False),
    Column("user_name", String, nullable=False),
    Column("at", DateTime, nullable=False),
    Column("action", String, nullable=False),
    Column("fare", Float),
    Column("reason", Text),
    Column("category", String),
    Column("engine_fare", Float),
    Column("our_fare", Float),
    # what the suggestion was built from, so a decision can be traced and used to retrain
    Column("rules_version", Integer),
    Column("model_version", String),
    Column("predicted_fare", Float),
    Column("floor_value", Float),
)
OUTCOME_COLUMNS = (outcomes_calc.service_outcomes.c.final_seats, outcomes_calc.service_outcomes.c.final_revenue)

CATEGORIES = {"pace_misread", "rival_data_wrong", "cost_wrong", "event_missed", "other"}


class DecisionIn(BaseModel):
    action: Literal["approve", "change", "reject", "wrong"]
    fare: float | None = None
    reason: str | None = None
    category: str | None = None


class AlreadyDecided(Exception):
    def __init__(self, prior: dict):
        self.prior = prior


class NotAllowed(Exception):
    def __init__(self, errors: list[dict]):
        self.errors = errors


def _row(r) -> dict:
    d = dict(r._mapping)
    d["id"] = str(d["id"])
    d["user"] = d.pop("user_name")
    d.pop("user_id")
    d["at"] = d["at"].isoformat()
    seats, revenue = d.pop("final_seats", None), d.pop("final_revenue", None)
    # None until a real file of final seats and revenue is loaded (scripts/load_outcomes.py)
    d["outcome"] = None if seats is None or pd.isna(seats) else dict(final_seats=float(seats), revenue=float(revenue))
    return d


def ensure_table(engine) -> None:
    """Create the tables, and add any column an older `decisions` table is missing (create_all never alters)."""
    outcomes_calc.ensure_table(engine)
    metadata.create_all(engine, tables=[decisions])
    have = {c["name"] for c in inspect(engine).get_columns("decisions")}
    missing = [c for c in decisions.columns if c.name not in have]
    if missing:
        with engine.begin() as con:
            for c in missing:
                con.execute(text(f'ALTER TABLE decisions ADD COLUMN {c.name} {c.type.compile(dialect=engine.dialect)}'))


def list_decisions(engine, service_id: str | None = None) -> list[dict]:
    ensure_table(engine)
    q = (select(decisions, *OUTCOME_COLUMNS)
         .select_from(decisions.outerjoin(outcomes_calc.service_outcomes,
                                          decisions.c.service_id == outcomes_calc.service_outcomes.c.service_id))
         .order_by(decisions.c.at.desc(), decisions.c.id.desc()))
    if service_id:
        q = q.where(decisions.c.service_id == service_id)
    with engine.connect() as con:
        return [_row(r) for r in con.execute(q)]


def decided_service_ids(engine) -> set[str]:
    ensure_table(engine)
    with engine.connect() as con:
        return {r[0] for r in con.execute(select(decisions.c.service_id).distinct())}


def validate(body: DecisionIn, suggested_fare: float | None, allowed: list[float]) -> list[dict]:
    """Field errors in the same shape FastAPI uses for 422."""
    errors = []

    def add(field: str, msg: str):
        errors.append({"loc": ["body", field], "msg": msg})

    if body.action == "approve" and suggested_fare is None:
        add("action", "There is no suggested fare to approve")
    if body.action == "change" and (body.fare is None or body.fare not in allowed):
        add("fare", "Fare is not an allowed fare step that passes the rules")
    if body.action != "approve" and not (body.reason or "").strip():
        add("reason", "A reason is required")
    if body.action == "wrong" and body.category not in CATEGORIES:
        add("category", "Choose a category")
    return errors


def record_decision(engine, service_id: str, user: dict, body: DecisionIn, suggestion: dict, allowed: list[float]) -> dict:
    """Validate and store one decision. Raises AlreadyDecided (409) or NotAllowed (422)."""
    ensure_table(engine)
    prior = list_decisions(engine, service_id)
    if prior:
        raise AlreadyDecided(prior[-1])
    errors = validate(body, suggestion["suggested_fare"], allowed)
    if errors:
        raise NotAllowed(errors)
    fare = body.fare if body.action == "change" else suggestion["suggested_fare"] if body.action == "approve" else None
    values = dict(service_id=service_id, user_id=user["id"], user_name=user["name"], at=datetime.now(),
                  action=body.action, fare=fare, reason=(body.reason or "").strip() or None,
                  category=body.category, engine_fare=suggestion["engine_fare"], our_fare=suggestion["suggested_fare"],
                  rules_version=suggestion.get("rules_version"), floor_value=suggestion.get("floor_value"),
                  model_version=(suggestion.get("predicted_fare") or {}).get("model_version"),
                  predicted_fare=(suggestion.get("predicted_fare") or {}).get("mid"))
    with engine.begin() as con:
        new_id = con.execute(insert(decisions).values(**values)).inserted_primary_key[0]
        row = con.execute(select(decisions).where(decisions.c.id == new_id)).one()
    return _row(row)


def decide(engine, service_id: str, user: dict, body: DecisionIn) -> dict | None:
    """Load the service, build its suggestion and allowed fares, and record the decision. None = unknown service."""
    inp = load_inputs(engine, service_id)
    if inp is None:
        return None
    suggestion = build_suggestion(inp["svc"], inp["rules"], inp["seat_fn"], inp["band"], inp["rivals"])
    allowed = [r["fare"] for r in what_if_rows(inp["svc"], inp["rules"], inp["seat_fn"]) if not r["blocked_by"]]
    return record_decision(engine, service_id, user, body, suggestion, allowed)
