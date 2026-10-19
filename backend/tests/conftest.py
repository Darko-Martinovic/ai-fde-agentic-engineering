import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    """Give every test its own fresh database."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "undercover.db"))


@pytest.fixture
def client():
    return TestClient(app)
