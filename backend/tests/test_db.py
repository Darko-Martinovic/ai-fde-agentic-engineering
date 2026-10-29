import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool, QueuePool

from backend import db


def test_without_database_url_the_records_are_in_sqlite(monkeypatch, tmp_path):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "records.db"))
    engine = db.engine()
    assert engine.dialect.name == "sqlite"
    assert engine.url.database == str(tmp_path / "records.db")
    assert isinstance(engine.pool, NullPool)


def test_with_database_url_the_records_are_on_postgres(monkeypatch):
    """Built without connecting: the engine opens no connection until it's used."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://someone:secret@db.example:5432/x")
    engine = db.engine()
    assert engine.url.drivername == "postgresql+psycopg"
    assert isinstance(engine.pool, QueuePool)
    assert engine.pool.size() == 4
    assert engine.pool._max_overflow == 0  # noqa: SLF001 - no public way to read it
    assert engine.pool.timeout() == 25


def test_postgres_connections_use_undercovers_schema(monkeypatch):
    made = {}
    monkeypatch.setattr(
        db, "create_engine", lambda url, **options: made.update(options)
    )
    db.engine_for("postgresql+psycopg://someone@db.example/schema-test")
    db.engine_for.cache_clear()
    assert made["connect_args"] == {"options": "-c search_path=undercover"}


def test_an_empty_database_url_is_sqlite(monkeypatch):
    """As the end-to-end tests set it, so a developer's Supabase is never reached."""
    monkeypatch.setenv("DATABASE_URL", "")
    assert db.engine().dialect.name == "sqlite"


def test_a_postgres_url_gets_psycopg_whatever_its_scheme(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://someone:secret@db.example/x")
    assert db.postgres_url() == "postgresql+psycopg://someone:secret@db.example/x"


POOLER = "postgresql+psycopg://undercover:secret@pooler.example:6543/postgres"


@pytest.fixture
def made(monkeypatch):
    """What each engine is made with, in place of making one."""
    calls = []

    def record(url, **options):
        calls.append(options)
        return create_engine("sqlite://", poolclass=options.get("poolclass", NullPool))

    monkeypatch.setattr(db, "create_engine", record)
    db.engine_for.cache_clear()
    yield calls
    db.engine_for.cache_clear()


def test_on_lambda_each_request_opens_its_own_connection_without_prepared_statements(
    monkeypatch, made
):
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "undercover-app")
    db.engine_for(POOLER)
    [options] = made
    assert options["poolclass"] is NullPool
    assert options["connect_args"]["prepare_threshold"] is None
    assert options["connect_args"]["options"] == f"-c search_path={db.schema()}"


def test_off_lambda_the_pool_is_as_before(monkeypatch, made):
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    db.engine_for(POOLER)
    [options] = made
    assert "poolclass" not in options
    assert "prepare_threshold" not in options["connect_args"]
    assert options["pool_size"] == 4
