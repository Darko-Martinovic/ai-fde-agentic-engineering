import pytest

from backend import db, runner


class FakeProcess:
    """Stands in for the agent's process, so no model is called."""

    def __init__(self, claim_ids):
        self.claim_ids = claim_ids
        self.alive = True

    def is_alive(self):
        return self.alive

    def terminate(self):
        self.alive = False

    def join(self, timeout=None):
        pass


@pytest.fixture(autouse=True)
def fake_process(monkeypatch):
    started = []

    def start(claim_ids):
        started.append(FakeProcess(claim_ids))
        return started[-1]

    monkeypatch.setattr(runner, "start_process", start)
    yield started
    runner.RUN.process = None
    runner.RUN.mode = None


def test_idle(client):
    assert client.get("/api/agent").json() == {
        "running": False,
        "mode": None,
        "claim_id": None,
    }


def test_run_claim(client, fake_process):
    response = client.post("/api/agent/claims/CLM-1001")
    assert response.status_code == 200
    assert response.json() == {"running": True, "mode": "claim", "claim_id": None}
    assert fake_process[0].claim_ids == ["CLM-1001"]
    client.post("/api/claims/CLM-1001/start")
    assert client.get("/api/agent").json()["claim_id"] == "CLM-1001"


def test_one_run_at_a_time(client):
    client.post("/api/agent/claims/CLM-1001")
    for path in ["/api/agent/claims/CLM-1002", "/api/agent/queue"]:
        response = client.post(path)
        assert response.status_code == 409
        assert response.json()["detail"] == "The agent is already running"


def test_run_needs_a_waiting_claim(client):
    client.post("/api/claims/CLM-1001/start")
    response = client.post("/api/agent/claims/CLM-1001")
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 is in_progress, not waiting"
    assert client.post("/api/agent/claims/CLM-9999").status_code == 404


def test_run_queue(client, fake_process):
    response = client.post("/api/agent/queue")
    assert response.json() == {"running": True, "mode": "queue", "claim_id": None}
    assert fake_process[0].claim_ids == []


def test_run_queue_with_nothing_waiting(client):
    client.get("/api/claims")
    conn = db.connect()
    with conn:
        conn.execute("UPDATE claims SET status = 'decided'")
    conn.close()
    response = client.post("/api/agent/queue")
    assert response.status_code == 409
    assert response.json()["detail"] == "No claims are waiting"


def test_finished_run_is_not_running(client, fake_process):
    client.post("/api/agent/queue")
    fake_process[0].alive = False
    assert client.get("/api/agent").json()["running"] is False
    assert client.post("/api/agent/claims/CLM-1001").status_code == 200


def test_stop(client, fake_process):
    client.post("/api/agent/claims/CLM-1001")
    client.post("/api/claims/CLM-1001/start")
    client.post(
        "/api/claims/CLM-1001/steps",
        json={"thread_id": "t-1", "kind": "tool_call", "text": "get_claim"},
    )
    client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "approve",
            "payout": 420,
            "reasons": "Covered.",
            "policy_section": "Section 3, Trip Delay",
        },
    )
    response = client.post("/api/agent/stop")
    assert response.json() == {"running": False, "mode": None, "claim_id": None}
    assert fake_process[0].alive is False
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "waiting"
    assert claim["decisions"] == []
    assert len(client.get("/api/claims/CLM-1001/steps").json()) == 1


def test_stop_keeps_decided_claims(client):
    client.post("/api/claims/CLM-1002/start")
    client.post(
        "/api/claims/CLM-1002/decision",
        json={
            "decision": "approve",
            "payout": 1150,
            "reasons": "Covered.",
            "policy_section": "Section 5, Baggage",
        },
    )
    client.post("/api/agent/stop")
    claim = client.get("/api/claims/CLM-1002").json()
    assert claim["status"] == "awaiting_sign_off"
    assert len(claim["decisions"]) == 1
