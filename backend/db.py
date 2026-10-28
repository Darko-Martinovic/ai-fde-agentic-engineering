"""The UnderCover database: its tables, written once for SQLite and Postgres, and
the engine. With DATABASE_URL in the environment the records are on Postgres
(Supabase), in a schema of their own set on every connection, so the queries are
the same on both; without it, they're in the SQLite file in UNDERCOVER_DB, as
in the tests."""

from functools import cache

from sqlalchemy import (
    DDL,
    Boolean,
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

# The tables for improving the claim agent are part of the same schema
from backend import db_improvement  # noqa: F401
from backend.config import database_path
from backend.schema import counter, metadata, text_column
from settings import optional_setting, setting

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
    # An evaluation's copy of a claim: the evaluation, and the claim it copies.
    # Copies stay out of the queue.
    Column("evaluation_id", Integer, nullable=True),
    text_column("copy_of", nullable=True),
)
# The answer key, which seeding loads: the held-out claims, out of the queue, and
# the handlers' decisions on both labelled sets. No claim operation reads these.
held_out_claims = Table(
    "held_out_claims",
    metadata,
    text_column("claim_id", primary_key=True),
    text_column("data"),
)
handler_decisions = Table(
    "handler_decisions",
    metadata,
    text_column("evaluation_set", primary_key=True),
    text_column("claim_id", primary_key=True),
    text_column("decision"),
    Column("payout", Float, nullable=False),
    Column("tiny", Boolean, nullable=False),
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
    # Who a sign-in is: the email a handler signs in with
    Column("email", Text, nullable=False, unique=True),
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
    # The approval limit when the decision was recorded, which a payout over it
    # waits for a handler's sign-off under, whatever the limit becomes
    Column("approval_limit", Float, nullable=False),
    # A handler's review of a held payout: signed_off or rejected, by whom, when,
    # and a rejection's note
    text_column("review", nullable=True),
    text_column("reviewed_by", nullable=True),
    text_column("reviewed_at", nullable=True),
    text_column("review_note", nullable=True),
    sqlite_autoincrement=True,
)
# A dispatch or an evaluation: N claim agents at once on the claims of the
# queue, or on copies of a labelled set's claims (all of them, or its tiny
# ones), on a version of the claim agent's configuration, whose model and
# reasoning effort it keeps too, and an evaluation in a round of improvement
# names its round. Its summary, built from the records when it finishes, is
# kept as JSON.
runs = Table(
    "runs",
    metadata,
    counter("run_id"),
    text_column("kind"),
    Column("agents", Integer, nullable=False),
    Column("version", Integer, nullable=False),
    text_column("model"),
    text_column("reasoning_effort"),
    Column("round_id", Integer, nullable=True),
    text_column("evaluation_set", nullable=True),
    Column("tiny", Boolean, nullable=True),
    text_column("status"),
    text_column("started_at"),
    text_column("finished_at", nullable=True),
    text_column("summary", nullable=True),
    sqlite_autoincrement=True,
)
# The claims a run works, in the order it takes them
run_claims = Table(
    "run_claims",
    metadata,
    Column("run_id", Integer, primary_key=True),
    Column("position", Integer, primary_key=True),
    text_column("claim_id"),
)
attempts = Table(
    "attempts",
    metadata,
    counter("attempt_id"),
    Column("run_id", Integer, nullable=True),
    text_column("claim_id"),
    text_column("thread_id"),
    text_column("started_at"),
    sqlite_autoincrement=True,
)
# Each model call a claim agent makes, and each spell of its work on a claim,
# with the run it happened in, or none
model_calls = Table(
    "model_calls",
    metadata,
    counter("model_call_id"),
    text_column("claim_id"),
    text_column("thread_id"),
    Column("run_id", Integer, nullable=True),
    text_column("model"),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("cost", Float, nullable=False),
    Column("seconds", Float, nullable=False),
    text_column("recorded_at"),
    sqlite_autoincrement=True,
)
work_times = Table(
    "work_times",
    metadata,
    counter("work_time_id"),
    text_column("claim_id"),
    text_column("thread_id"),
    Column("run_id", Integer, nullable=True),
    text_column("started_at"),
    Column("seconds", Float, nullable=False),
    sqlite_autoincrement=True,
)
payments = Table(
    "payments",
    metadata,
    text_column("claim_id", primary_key=True),
    Column("amount", Float, nullable=False),
    text_column("authorized_by"),
    text_column("paid_at"),
    text_column("signed_off_at", nullable=True),
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
        # Many claim agents at once share the pool: wait for a connection
        pool_timeout=int(setting("DATABASE_WAIT_SECONDS")),
        pool_pre_ping=True,
    )


def has_tables(conn: Connection) -> bool:
    """Whether every table is there, as it isn't before a build's first seed."""
    found = inspect(conn)
    return all(found.has_table(name) for name in metadata.tables)


def create_tables(conn: Connection) -> None:
    metadata.create_all(conn)


# Tables earlier builds made, which seeding drops so none is left behind: the
# queue agent's model calls, which claims' model calls replaced
RETIRED = ("usage",)


def drop_tables(conn: Connection) -> None:
    """Drop the backend's tables, and those it no longer has, leaving any others,
    such as the agent's checkpoints, alone."""
    metadata.drop_all(conn)
    for name in RETIRED:
        Table(name, MetaData()).drop(conn, checkfirst=True)


def where(engine: Engine) -> str:
    """Where an engine's records are, to say so."""
    if engine.dialect.name == "postgresql":
        return f"the {schema()} schema on Postgres"
    return str(engine.url.database)
