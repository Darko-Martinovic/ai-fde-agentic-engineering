import pytest
from fastapi.testclient import TestClient

from agent import api, harness
from agent.tests.stub import FREE
from backend.main import app


@pytest.fixture(autouse=True)
def backend(tmp_path, monkeypatch):
    """Point the agent at the real backend, in process, on a fresh database."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "undercover.db"))
    monkeypatch.setattr(api, "client", lambda: TestClient(app))
    monkeypatch.setattr(harness, "RETRY_DELAY", 0)
    return TestClient(app)


@pytest.fixture
def run(backend):
    """A run to work claims in, on a free model."""
    return api.start_run("queue", 25, FREE.spec)["run_id"]
