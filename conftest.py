import os

# Tests read only the committed defaults, never a developer's .env, never reach
# Supabase, and send nothing to Langfuse. This runs before any test module
# imports a config module.
os.environ["UNDERCOVER_ENV_FILES"] = ".env.defaults"
os.environ.pop("DATABASE_URL", None)
os.environ["LANGFUSE_TRACING_ENABLED"] = "false"

from contextlib import contextmanager  # noqa: E402 - after the settings above

import pytest  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from agent import checkpoints  # noqa: E402


@pytest.fixture(autouse=True)
def memory_saver(monkeypatch):
    """The claim graph saves its progress in memory, never on Postgres. Returns
    the saver a command-line run opens."""
    saver = InMemorySaver()

    @contextmanager
    def in_memory():
        yield saver

    monkeypatch.setattr(checkpoints, "saver", in_memory)
    return saver
