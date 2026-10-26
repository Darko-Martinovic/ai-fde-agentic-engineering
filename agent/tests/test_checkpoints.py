from contextlib import contextmanager

import pytest
from psycopg.rows import dict_row

from agent import checkpoints
from agent.checkpoints import saver as real_saver  # before the tests' own saver


def test_the_saver_needs_postgres(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"), real_saver():
        pass


def test_the_saver_keeps_a_small_pool_in_undercovers_schema(monkeypatch):
    """Built without connecting: the pool and the saver are stand-ins."""
    made = {}
    done = []

    class Pool:
        check_connection = None

        def __init__(self, url, **options):
            made.update(options, url=url)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        @contextmanager
        def connection(self):
            yield "connection"

    class Saver:
        def __init__(self, pool):
            self.pool = pool

        def setup(self):
            done.append("setup")

    monkeypatch.setenv("DATABASE_URL", "postgresql://someone@db.example/x")
    monkeypatch.setattr(checkpoints, "ConnectionPool", Pool)
    monkeypatch.setattr(checkpoints, "PostgresSaver", Saver)
    monkeypatch.setattr(
        checkpoints, "create_schema", lambda conn, schema: done.append(schema)
    )
    monkeypatch.setattr(
        checkpoints,
        "enable_row_level_security",
        lambda conn, schema: done.append("rls"),
    )
    with real_saver() as saver:
        assert isinstance(saver, Saver)
    assert (made["min_size"], made["max_size"]) == (1, 4)
    assert made["kwargs"] == {
        "autocommit": True,
        "prepare_threshold": 0,
        "row_factory": dict_row,
        "options": "-c search_path=undercover",
    }
    assert done == ["undercover", "setup", "rls"]
