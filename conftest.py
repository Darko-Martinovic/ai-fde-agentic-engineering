import os

# Tests read only the committed defaults, never a developer's .env, never reach
# Supabase, and send nothing to Langfuse. This runs before any test module
# imports a config module.
os.environ["UNDERCOVER_ENV_FILES"] = "settings/.env.defaults"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("MODEL_NAME", None)
os.environ["LANGFUSE_TRACING_ENABLED"] = "false"

from contextlib import contextmanager  # noqa: E402 - after the settings above

import pytest  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from agent import checkpoints  # noqa: E402
from backend import auth, judge  # noqa: E402
from backend.tests.judge_answers import B  # noqa: E402
from backend.tests.sign_ins import AGENT_KEY, Keys  # noqa: E402

os.environ["UNDERCOVER_API_KEY"] = AGENT_KEY


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


@pytest.fixture(autouse=True)
def sign_in_keys(monkeypatch):
    """Sign-ins are checked against the test's key, never Supabase's."""
    monkeypatch.setattr(auth, "keys", Keys)


@pytest.fixture(autouse=True)
def judged(monkeypatch):
    """The judge grades every claim B, never reaching OpenRouter; the states
    it was asked about."""
    asked = []

    def ask(state):
        asked.append(state)
        return B

    monkeypatch.setattr(judge, "ask", ask)
    monkeypatch.setattr(judge, "client", object)
    return asked
