"""Module C: final outcome of a departed service (seats and revenue after departure).

The data only has booking-time seat snapshots, so there is no outcome until a real file of final seats and
revenue is loaded (scripts/load_outcomes.py). Nothing here is estimated or filled in.
"""
from datetime import datetime

import pandas as pd
from sqlalchemy import Column, DateTime, Float, MetaData, String, Table, delete, insert

metadata = MetaData()
service_outcomes = Table(
    "service_outcomes", metadata,
    Column("service_id", String, primary_key=True),
    Column("final_seats", Float, nullable=False),
    Column("final_revenue", Float, nullable=False),
    Column("loaded_at", DateTime, nullable=False),
    Column("source", String),
)

REQUIRED = ["service_id", "final_seats", "final_revenue"]


def ensure_table(engine) -> None:
    metadata.create_all(engine, tables=[service_outcomes])


def validate_rows(rows: pd.DataFrame, services: pd.DataFrame, now: datetime) -> tuple[pd.DataFrame, list[dict]]:
    """Split the file into rows safe to store and rejected rows with the reason. `services` needs service_id,
    departure_at and total_seats."""
    missing = [c for c in REQUIRED if c not in rows.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    svc = services.set_index("service_id")
    good, rejected = [], []
    for r in rows.itertuples(index=False):
        sid = str(r.service_id).strip()
        seats, revenue = pd.to_numeric(r.final_seats, errors="coerce"), pd.to_numeric(r.final_revenue, errors="coerce")
        if sid not in svc.index:
            why = "unknown service"
        elif svc.at[sid, "departure_at"] >= now:
            why = "service has not departed yet"
        elif pd.isna(seats) or pd.isna(revenue):
            why = "final seats and revenue must be numbers"
        elif not 0 <= seats <= svc.at[sid, "total_seats"]:
            why = f"final seats must be between 0 and {int(svc.at[sid, 'total_seats'])}"
        elif revenue < 0:
            why = "revenue cannot be negative"
        else:
            good.append(dict(service_id=sid, final_seats=float(seats), final_revenue=float(revenue)))
            continue
        rejected.append(dict(service_id=sid, reason=why))
    out = pd.DataFrame(good, columns=REQUIRED).drop_duplicates("service_id", keep="last")
    return out, rejected


def store(engine, rows: pd.DataFrame, source: str) -> int:
    """Insert or replace one outcome per service. Returns how many were stored."""
    ensure_table(engine)
    now = datetime.now()
    records = [dict(service_id=r.service_id, final_seats=r.final_seats, final_revenue=r.final_revenue,
                    loaded_at=now, source=source) for r in rows.itertuples(index=False)]
    if not records:
        return 0
    with engine.begin() as con:
        con.execute(delete(service_outcomes).where(service_outcomes.c.service_id.in_([r["service_id"] for r in records])))
        con.execute(insert(service_outcomes), records)
    return len(records)
