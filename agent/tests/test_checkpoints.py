from contextlib import contextmanager

import pytest
from psycopg.rows import dict_row

from agent import checkpoints

# Before the tests' own pool and saver stand in for them
from agent.checkpoints import pool as real_pool
from agent.checkpoints import saver as real_saver


def test_the_pool_needs_postgres(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"), real_pool():
        pass


def test_the_pool_is_small_waits_for_a_connection_and_sets_up_once(monkeypatch):
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
        def __init__(self, connections):
            self.connections = connections

        def setup(self):
            done.append("setup")

    monkeypatch.setenv("DATABASE_URL", "postgresql://someone@db.example/x")
    monkeypatch.setattr(checkpoints, "ConnectionPool", Pool)
    monkeypatch.setattr(checkpoints, "PostgresSaver", Saver)
    monkeypatch.setattr(checkpoints, "saver", real_saver)
    monkeypatch.setattr(
        checkpoints, "create_schema", lambda conn, schema: done.append(schema)
    )
    monkeypatch.setattr(
        checkpoints,
        "enable_row_level_security",
        lambda conn, schema: done.append("rls"),
    )
    with real_pool() as connections:
        assert isinstance(connections, Pool)
        first, second = real_saver(connections), real_saver(connections)
    assert (made["min_size"], made["max_size"], made["timeout"]) == (1, 4, 120)
    assert made["kwargs"] == {
        "autocommit": True,
        "prepare_threshold": 0,
        "row_factory": dict_row,
        "options": "-c search_path=undercover",
    }
    assert done == ["undercover", "setup", "rls"]
    assert isinstance(first, Saver)
    assert isinstance(second, Saver)
    assert first is not second
    assert first.connections is second.connections is connections
