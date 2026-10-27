from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, Text, inspect

from app.db import engine
from app.models import metadata

KIND = {"TEXT": Text, "BIGINT": BigInteger, "DOUBLE PRECISION": Float, "TIMESTAMP": DateTime,
        "BOOLEAN": Boolean, "INTEGER": Integer}


def test_models_match_live_database():
    """If this fails, a script changed a column: update app/models.py and tell Module B's owner."""
    live = inspect(engine)
    assert set(metadata.tables) <= set(live.get_table_names())
    for name, table in metadata.tables.items():
        got = {c["name"]: KIND[str(c["type"])] for c in live.get_columns(name)}
        want = {c.name: type(c.type) for c in table.columns}
        assert got == want, name
