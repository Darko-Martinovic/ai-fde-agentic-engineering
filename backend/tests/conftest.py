import json

import pytest
from fastapi.testclient import TestClient

from backend import db
from backend.main import app
from backend.store import records


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    """Give every test its own fresh database."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "undercover.db"))


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def approval_limit(client):
    """Change the payout approval limit stored with the company's rules."""

    def change(amount):
        client.get("/api/claims")
        conn = db.connect()
        rules = json.loads(records.stored(conn, "company"))
        rules["payout_approval_limit"] = amount
        with conn:
            conn.execute(
                "UPDATE settings SET value = ? WHERE name = 'company'",
                (json.dumps(rules),),
            )
        conn.close()

    return change
