import pytest
from fastapi.testclient import TestClient

from backend import agent_service
from backend.main import app
from backend.tests.sign_ins import agent_headers, both_sides


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    """Give every test its own fresh database."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "undercover.db"))


@pytest.fixture
def client():
    """A client that plays the agent's moves and reads as Dana Whitfield."""
    return TestClient(app, headers=both_sides())


@pytest.fixture
def agent_client():
    """A client with only the agent's key, signed in as nobody."""
    return TestClient(app, headers=agent_headers())


@pytest.fixture(autouse=True)
def resumed(monkeypatch):
    """Stand in for the agent's service: the claims it was asked to pick up."""
    asked = []
    monkeypatch.setattr(agent_service, "resume_claim", asked.append)
    return asked
