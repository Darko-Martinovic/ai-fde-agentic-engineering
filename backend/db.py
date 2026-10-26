"""The UnderCover database: its tables, written once for SQLite and Postgres, and
the engine. With DATABASE_URL in the environment the records are on Postgres
(Supabase), in a schema of their own set on every connection, so the queries are
the same on both; without it, they're in the SQLite file in UNDERCOVER_DB, as
in the tests."""

from functools import cache

from sqlalchemy import (
    DDL,
    Column,
    Connection,
    Engine,
    Float,
    Integer,
    MetaData,
    Table,
    Text,
    create_engine,
    event,
    inspect,
    make_url,
)
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema

from backend.config import database_path
from settings import optional_setting, setting

metadata = MetaData()


def text_column(
    name: str, *, nullable: bool = False, primary_key: bool = False
) -> Column:
    """A column of text, required unless it's nullable."""
    return Column(name, Text, nullable=nullable, primary_key=primary_key)


def counter(name: str) -> Column:
    """A key that counts up, as each row is added."""
    return Column(name, Integer, primary_key=True, autoincrement=True)


# Records seeded from data/ keep their JSON as text, as they came
claims = Table(
    "claims",
    metadata,
    text_column("claim_id", primary_key=True),
    text_column("policy_id"),
    text_column("customer_id"),
    text_column("status"),
    text_column("data"),
    # Counts the changes to the claim's decision and payment, so two at once
    # can't both be recorded
    Column("revision", Integer, nullable=False, default=0),
)
policies = Table(
    "policies",
    metadata,
    text_column("policy_id", primary_key=True),
    text_column("data"),
)
customers = Table(
    "customers",
    metadata,
    text_column("customer_id", primary_key=True),
    text_column("data"),
)
handlers = Table(
    "handlers",
    metadata,
    text_column("handler_id", primary_key=True),
    text_column("data"),
)
settings = Table(
    "settings", metadata, text_column("name", primary_key=True), text_column("value")
)
steps = Table(
    "steps",
    metadata,
    counter("step_id"),
    text_column("claim_id"),
    text_column("thread_id"),
    text_column("kind"),
    text_column("text"),
    text_column("recorded_at"),
    sqlite_autoincrement=True,
)
decisions = Table(
    "decisions",
    metadata,
    counter("decision_id"),
    text_column("claim_id"),
    text_column("decided_by"),
    text_column("decision"),
    Column("payout", Float, nullable=False),
    text_column("reasons"),
    text_column("policy_section", nullable=True),
    text_column("decided_at"),
    sqlite_autoincrement=True,
)
runs = Table(
    "runs",
    metadata,
    counter("run_id"),
    text_column("mode"),
    Column("cap", Integer, nullable=False),
    text_column("model"),
    text_column("status"),
    text_column("started_at"),
    text_column("finished_at", nullable=True),
    text_column("summary", nullable=True),
    text_column("todos"),
    sqlite_autoincrement=True,
)
attempts = Table(
    "attempts",
    metadata,
    counter("attempt_id"),
    Column("run_id", Integer, nullable=False),
    text_column("claim_id"),
    text_column("thread_id"),
    text_column("started_at"),
    sqlite_autoincrement=True,
)
usage = Table(
    "usage",
    metadata,
    counter("usage_id"),
    Column("run_id", Integer, nullable=False),
    text_column("claim_id", nullable=True),
    text_column("model"),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("cost", Float, nullable=False),
    Column("seconds", Float, nullable=False),
    text_column("recorded_at"),
    sqlite_autoincrement=True,
)
payments = Table(
    "payments",
    metadata,
    text_column("claim_id", primary_key=True),
    Column("amount", Float, nullable=False),
    text_column("authorized_by"),
    text_column("paid_at"),
)


# Supabase's API roles have no access to UnderCover's schema. Row level security
# with no policies keeps them out even if the schema were exposed, and doesn't
# bind the backend, which connects as the tables' owner.
for table in metadata.tables.values():
    event.listen(
        table,
        "after_create",
        DDL("ALTER TABLE %(fullname)s ENABLE ROW LEVEL SECURITY").execute_if(
            dialect="postgresql"
        ),
    )


@event.listens_for(metadata, "before_create")
def create_schema(target: MetaData, connection: Connection, **kw: object) -> None:
    """On Postgres, make UnderCover's schema before its tables, if it isn't there."""
    if connection.dialect.name == "postgresql":
        connection.execute(CreateSchema(schema(), if_not_exists=True))


def schema() -> str:
    """The Postgres schema UnderCover's tables are in."""
    return setting("DATABASE_SCHEMA")


def postgres_url() -> str | None:
    """Postgres's address from DATABASE_URL, for psycopg, or None for SQLite."""
    url = optional_setting("DATABASE_URL")
    return (
        make_url(url)
        .set(drivername="postgresql+psycopg")
        .render_as_string(hide_password=False)
        if url
        else None
    )


def engine() -> Engine:
    """The engine for the database the settings name."""
    return engine_for(postgres_url() or f"sqlite:///{database_path()}")


@cache
def engine_for(url: str) -> Engine:
    """One engine for each database. Postgres keeps a small pool, as Supabase's
    free plan allows 15 connections across every process; SQLite opens a
    connection for each request, so no file is held open."""
    if url.startswith("sqlite"):
        return create_engine(url, poolclass=NullPool)
    return create_engine(
        url,
        connect_args={"options": f"-c search_path={schema()}"},
        pool_size=int(setting("DATABASE_CONNECTIONS")),
        max_overflow=0,
        pool_pre_ping=True,
    )


def has_tables(conn: Connection) -> bool:
    return inspect(conn).has_table(claims.name)


def create_tables(conn: Connection) -> None:
    metadata.create_all(conn)


def drop_tables(conn: Connection) -> None:
    """Drop the backend's tables, leaving any others, such as the agent's
    checkpoints, alone."""
    metadata.drop_all(conn)


def where(engine: Engine) -> str:
    """Where an engine's records are, to say so."""
    if engine.dialect.name == "postgresql":
        return f"the {schema()} schema on Postgres"
    return str(engine.url.database)
