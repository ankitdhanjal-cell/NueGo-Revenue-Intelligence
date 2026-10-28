"""Data refresh: run the pipeline steps in order and record each run in `pipeline_runs`."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, insert, select

metadata = MetaData()
pipeline_runs = Table(
    "pipeline_runs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("started_at", DateTime, nullable=False),
    Column("finished_at", DateTime, nullable=False),
    Column("status", String, nullable=False),
    Column("steps_done", Text),
    Column("error", Text),
)


def run(engine, steps: list[tuple[str, callable]]) -> None:
    """Run each (name, function) in order. A failure stops the run, is recorded, and is raised again."""
    metadata.create_all(engine, tables=[pipeline_runs])
    started, done, status, error = datetime.now(), [], "ok", None
    try:
        for name, fn in steps:
            fn()
            done.append(name)
    except Exception as e:
        status, error = "failed", f"{name}: {e}"
        raise
    finally:
        with engine.begin() as con:
            con.execute(insert(pipeline_runs).values(started_at=started, finished_at=datetime.now(), status=status,
                                                     steps_done=", ".join(done), error=error))


def last_run(engine) -> dict | None:
    metadata.create_all(engine, tables=[pipeline_runs])
    with engine.connect() as con:
        r = con.execute(select(pipeline_runs).order_by(pipeline_runs.c.id.desc()).limit(1)).first()
    if r is None:
        return None
    return dict(finished_at=r.finished_at.isoformat(), status=r.status, steps_done=r.steps_done, error=r.error)
