import pytest

from agent import harness
from agent.tests.conftest import backend  # noqa: F401 - the agent's backend
from bench.score import Answer


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    """Tests never call a model: a test that needs one gives it a stub."""

    def refuse(model):
        raise AssertionError(f"A test tried to call {model.spec}")

    monkeypatch.setattr(harness, "chat_model", refuse)


@pytest.fixture
def key():
    """Hand-made answers, not the handlers' own: CLM-1001 approved for $420.00,
    CLM-1005 declined, both tiny, and CLM-1002 approved for $1,150.00."""
    return {
        "CLM-1001": Answer("CLM-1001", "approve", 420.0, True),
        "CLM-1005": Answer("CLM-1005", "decline", 0.0, True),
        "CLM-1002": Answer("CLM-1002", "approve", 1150.0, False),
    }
