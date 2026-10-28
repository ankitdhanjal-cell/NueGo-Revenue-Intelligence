"""Module C: who owns which corridor. Used to send each early warning to the right person.

There is no owner in the data, so this starts empty and an admin assigns owners. It is local to this app;
nothing is sent to any other system.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, MetaData, String, Table, delete, insert, select

from app.config import USERS

metadata = MetaData()
corridor_owners = Table(
    "corridor_owners", metadata,
    Column("route_id", String, primary_key=True),
    Column("user_id", String, nullable=False),
    Column("assigned_by", String, nullable=False),
    Column("assigned_at", DateTime, nullable=False),
)


class UnknownRoute(Exception):
    pass


class UnknownUser(Exception):
    pass


def ensure_table(engine) -> None:
    metadata.create_all(engine, tables=[corridor_owners])


def owner_map(engine) -> dict[str, str]:
    """route_id -> user_id for every corridor that has an owner."""
    ensure_table(engine)
    with engine.connect() as con:
        return {r.route_id: r.user_id for r in con.execute(select(corridor_owners))}


def assign(engine, route_id: str, user_id: str | None, by: str, route_ids: list[str]) -> None:
    """Set (or clear, with user_id None) the owner of a corridor."""
    if route_id not in route_ids:
        raise UnknownRoute(route_id)
    if user_id is not None and user_id not in {u["id"] for u in USERS}:
        raise UnknownUser(user_id)
    ensure_table(engine)
    with engine.begin() as con:
        con.execute(delete(corridor_owners).where(corridor_owners.c.route_id == route_id))
        if user_id is not None:
            con.execute(insert(corridor_owners).values(route_id=route_id, user_id=user_id, assigned_by=by,
                                                       assigned_at=datetime.now()))


def view(engine, routes: list[dict]) -> list[dict]:
    """One row per corridor, with its owner if it has one."""
    ensure_table(engine)
    with engine.connect() as con:
        rows = {r.route_id: r for r in con.execute(select(corridor_owners))}
    names = {u["id"]: u["name"] for u in USERS}
    out = []
    for r in routes:
        o = rows.get(r["id"])
        out.append(dict(route_id=r["id"], route_label=r["label"], owner_id=o.user_id if o else None,
                        owner_name=names.get(o.user_id) if o else None, assigned_by=o.assigned_by if o else None,
                        assigned_at=o.assigned_at.isoformat() if o else None))
    return out
