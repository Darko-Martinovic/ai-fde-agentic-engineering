import os

# Tests read only the committed defaults, never a developer's .env, never reach
# Supabase, and send nothing to Langfuse. This runs before any test module
# imports a config module.
os.environ["UNDERCOVER_ENV_FILES"] = "settings/.env.defaults"
os.environ.pop("DATABASE_URL", None)
os.environ["LANGFUSE_TRACING_ENABLED"] = "false"

from contextlib import contextmanager  # noqa: E402 - after the settings above

import pytest  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from agent import checkpoints  # noqa: E402


@pytest.fixture(autouse=True)
def memory_saver(monkeypatch):
    """The claim graphs save their progress in memory, never on Postgres: the
    process's pool is nothing, and every claim run's saver is this one."""
    saver = InMemorySaver()

    @contextmanager
    def no_pool():
        yield None

    monkeypatch.setattr(checkpoints, "pool", no_pool)
    monkeypatch.setattr(checkpoints, "saver", lambda connections: saver)
    return saver
