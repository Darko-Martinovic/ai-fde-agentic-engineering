import pytest
from fastapi.testclient import TestClient

from agent import api
from backend.main import app


@pytest.fixture(autouse=True)
def backend(tmp_path, monkeypatch):
    """Point the agent at the real backend, in process, on a fresh database."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "undercover.db"))
    monkeypatch.setattr(api, "client", lambda: TestClient(app))
    return TestClient(app)
