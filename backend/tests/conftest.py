import pytest
from fastapi.testclient import TestClient

from backend import agent_service
from backend.main import app


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    """Give every test its own fresh database."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "undercover.db"))


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def resumed(monkeypatch):
    """Stand in for the agent's service: the claims it was asked to pick up."""
    asked = []
    monkeypatch.setattr(agent_service, "resume_claim", asked.append)
    return asked
