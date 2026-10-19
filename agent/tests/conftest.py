import pytest
from fastapi.testclient import TestClient

import agent.__main__ as cli
from agent import main
from backend.main import app


@pytest.fixture(autouse=True)
def backend(tmp_path, monkeypatch):
    """Point the agent at the real backend, in process, on a fresh database."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "undercover.db"))
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    monkeypatch.setattr(cli, "backend", lambda: TestClient(app))
    return TestClient(app)
