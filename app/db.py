"""Database connection, shared by the API and the pipeline scripts."""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

engine = create_engine(os.environ["DATABASE_URL"])


def write_table(df, table: str) -> None:
    """Replace the rows of an existing table. The table itself comes from the migrations.

    It never creates or alters a table, so the schema only changes through Alembic.
    A column in `df` that the table does not have makes this fail on purpose.
    """
    from sqlalchemy import inspect, text

    if table not in inspect(engine).get_table_names():
        raise SystemExit(f"table {table} does not exist: run `alembic upgrade head` first")
    with engine.begin() as conn:  # one transaction: all or nothing
        conn.execute(text(f'DELETE FROM "{table}"'))
        df.to_sql(table, conn, if_exists="append", index=False, method="multi", chunksize=500)
