"""Where the claim graph saves its progress: LangGraph's Postgres checkpointer,
in the same Supabase database and schema as UnderCover's records, as in
labs/week2day3.ipynb. The agent is synchronous, with the synchronous
checkpointer, because async Postgres connections don't work with Windows'
default event loop."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection, sql
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from settings import optional_setting, setting

# How long a claim agent waits for one of the pool's connections
POOL_WAIT_SECONDS = 120
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


Pool = ConnectionPool[Any]


@contextmanager
def pool() -> Iterator[Pool]:
    """Open the process's pool of at most DATABASE_CONNECTIONS connections, which
    every claim agent in it shares, waiting for one rather than failing, and
    make the checkpointer's tables the first time, with row level security on
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
        timeout=POOL_WAIT_SECONDS,
    ) as connections:
        with connections.connection() as conn:
            create_schema(conn, schema)
        saver(connections).setup()
        with connections.connection() as conn:
            enable_row_level_security(conn, schema)
        yield connections


def savers(connections: Pool) -> Callable[[], PostgresSaver]:
    """A new checkpointer on the pool for each claim run that asks."""
    return lambda: saver(connections)


def saver(connections: Pool) -> PostgresSaver:
    """A checkpointer for one claim run, on the process's pool. Each claim run
    has its own, since a checkpointer lets one read or write at a time."""
    return PostgresSaver(connections)  # type: ignore[arg-type]
