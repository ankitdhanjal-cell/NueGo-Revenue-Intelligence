"""Module B, step 1: pricing rules and allowed fare steps, stored in `pricing_rules`.

Every PUT adds a new version row; old rows are kept. The newest row is the active one and is
read from the database on every request, so a change applies without a restart.
This table is the ONE place for the floor switch point (Module A reads it from here).
"""
import json
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, model_validator
from sqlalchemy import Column, DateTime, Float, Integer, MetaData, String, Table, Text, insert, select

from app.config import DEFAULT_RULES

metadata = MetaData()
pricing_rules = Table(
    "pricing_rules", metadata,
    Column("version", Integer, primary_key=True, autoincrement=True),
    Column("floor_switch_hours", Float, nullable=False),
    Column("ceiling", Float, nullable=False),
    Column("state_cap", Float),
    Column("max_change_pct", Float, nullable=False),
    Column("min_minutes_between_changes", Integer, nullable=False),
    Column("seats_weight", Float, nullable=False),
    Column("fare_steps", Text, nullable=False),  # JSON list of numbers
    Column("updated_by", String),
    Column("updated_at", DateTime, nullable=False),
)


class RulesIn(BaseModel):
    """Body of PUT /rules. A bad value gives a 422 with the reason."""
    floor_switch_hours: float
    ceiling: float
    state_cap: float | None = None
    max_change_pct: float
    min_minutes_between_changes: int
    seats_weight: float
    fare_steps: list[float]
    updated_by: str | None = None

    @model_validator(mode="after")
    def check(self):
        steps = self.fare_steps
        problems = []
        if self.floor_switch_hours < 0:
            problems.append("floor_switch_hours must be >= 0")
        if self.ceiling <= 0:
            problems.append("ceiling must be > 0")
        if self.state_cap is not None and self.state_cap <= 0:
            problems.append("state_cap must be > 0 or null")
        if not 0 < self.max_change_pct <= 100:
            problems.append("max_change_pct must be > 0 and <= 100")
        if self.min_minutes_between_changes < 0:
            problems.append("min_minutes_between_changes must be >= 0")
        if self.seats_weight < 0:
            problems.append("seats_weight must be >= 0")
        if not steps or any(s <= 0 for s in steps):
            problems.append("fare_steps must be a non-empty list of positive numbers")
        elif any(b <= a for a, b in zip(steps, steps[1:])):
            problems.append("fare_steps must be unique and ascending")
        elif self.ceiling < steps[0]:
            problems.append("ceiling must be >= the smallest fare step")
        elif self.state_cap is not None and self.state_cap < steps[0]:
            problems.append("state_cap must be >= the smallest fare step")
        if problems:
            raise ValueError("; ".join(problems))
        return self


def _row_to_dict(row) -> dict:
    d = dict(row._mapping)
    d["fare_steps"] = json.loads(d["fare_steps"])
    d["updated_at"] = d["updated_at"].isoformat()
    return d


def ensure_rules(engine) -> None:
    """Create the table if needed and add the default row once (idempotent)."""
    metadata.create_all(engine, tables=[pricing_rules])
    with engine.begin() as con:
        if con.execute(select(pricing_rules.c.version).limit(1)).first() is None:
            save_rules(engine, RulesIn(**DEFAULT_RULES, updated_by="default (assumption)"), con)


def save_rules(engine, rules: RulesIn, con=None) -> dict:
    """Insert a new version (old versions stay). Returns the saved row."""
    values = rules.model_dump()
    values["fare_steps"] = json.dumps(values["fare_steps"])
    values["updated_at"] = datetime.now()

    def _save(c):
        version = c.execute(insert(pricing_rules).values(**values)).inserted_primary_key[0]
        return _row_to_dict(c.execute(select(pricing_rules).where(pricing_rules.c.version == version)).one())

    if con is not None:
        return _save(con)
    with engine.begin() as c:
        return _save(c)


def active_rules(engine) -> dict:
    """The newest version, read from the database each time (no cache)."""
    ensure_rules(engine)
    with engine.connect() as con:
        row = con.execute(select(pricing_rules).order_by(pricing_rules.c.version.desc()).limit(1)).one()
    return _row_to_dict(row)


@dataclass
class RuleContext:
    """Everything check_fare needs. No database access: build it from the rules row and the service."""
    current_fare: float
    floor: float
    ceiling: float
    state_cap: float | None
    max_change_pct: float
    min_minutes_between_changes: int
    minutes_since_last_change: float | None  # None = unknown (the data has no fare-change history)
    fare_steps: list[float]


def check_fare(fare: float, ctx: RuleContext) -> list[str]:
    """Codes of the rules `fare` breaks. An empty list means the fare is allowed."""
    out = []
    if not any(abs(fare - s) < 1e-9 for s in ctx.fare_steps):
        out.append("NOT_A_FARE_STEP")
    if fare < ctx.floor:
        out.append("BELOW_FLOOR")
    if fare > ctx.ceiling:
        out.append("ABOVE_CEILING")
    if ctx.state_cap is not None and fare > ctx.state_cap:
        out.append("ABOVE_STATE_CAP")
    if abs(fare - ctx.current_fare) > ctx.current_fare * ctx.max_change_pct / 100 + 1e-9:
        out.append("STEP_TOO_LARGE")
    too_soon = (ctx.minutes_since_last_change is not None
                and ctx.minutes_since_last_change < ctx.min_minutes_between_changes)
    if too_soon and abs(fare - ctx.current_fare) > 1e-9:
        out.append("TOO_SOON")
    return out
