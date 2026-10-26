"""Where the claim graph saves its progress: LangGraph's Postgres checkpointer,
in the same Supabase database and schema as UnderCover's records, as in
labs/week2day3.ipynb. The agent is synchronous, with the synchronous
checkpointer, because async Postgres connections don't work with Windows'
default event loop."""

from collections.abc import Iterator
from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection, sql
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from settings import optional_setting, setting

NO_DATABASE = (
    "The agent saves its progress on Postgres, so a handler's sign-off can pick a"
    " claim back up: set DATABASE_URL in .env"
)


def connection_options(schema: str) -> dict[str, object]:
    """What LangGraph's checkpointer needs on each connection, and the schema."""
    return {
        "autocommit": True,
        "prepare_threshold": 0,
        "row_factory": dict_row,
        "options": f"-c search_path={schema}",
    }


def create_schema(conn: Connection[DictRow], schema: str) -> None:
    conn.execute(
        sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))
    )


def enable_row_level_security(conn: Connection[DictRow], schema: str) -> None:
    """Turn row level security on for the checkpointer's tables, as for
    UnderCover's own: Supabase's API roles stay out, and the agent, which owns
    the tables, isn't bound by it."""
    tables = conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = %s AND NOT rowsecurity",
        (schema,),
    ).fetchall()
    for table in tables:
        conn.execute(
            sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(
                sql.Identifier(schema, table["tablename"])
            )
        )


@contextmanager
def saver() -> Iterator[PostgresSaver]:
    """Open the checkpointer on a pool of at most DATABASE_CONNECTIONS
    connections, making its tables the first time, with row level security on
    like UnderCover's own."""
    url = optional_setting("DATABASE_URL")
    if url is None:
        raise RuntimeError(NO_DATABASE)
    schema = setting("DATABASE_SCHEMA")
    with ConnectionPool(
        url,
        min_size=1,
        max_size=int(setting("DATABASE_CONNECTIONS")),
        kwargs=connection_options(schema),
        check=ConnectionPool.check_connection,
    ) as pool:
        with pool.connection() as conn:
            create_schema(conn, schema)
        checkpointer = PostgresSaver(pool)  # type: ignore[arg-type]
        checkpointer.setup()
        with pool.connection() as conn:
            enable_row_level_security(conn, schema)
        yield checkpointer
