import pytest

from backend import runner
from backend.tests.claim_starts import start
from backend.tests.direct_changes import set_status

MODEL = "Claude Haiku 5.5"
SPEC = "anthropic:claude-haiku-5-5"
ON_A_MODEL = {"model": SPEC}
QUEUE = {"model": SPEC, "cap": 5}


class FakeProcess:
    """Stands in for the agent's process, so no model is called."""

    def __init__(self, arguments):
        self.arguments = arguments
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

    def start(arguments):
        started.append(FakeProcess(arguments))
        return started[-1]

    monkeypatch.setattr(runner, "start_process", start)
    yield started
    runner.RUN.process = None
    runner.RUN.mode = None
    runner.RUN.model = None


def test_idle(client):
    assert client.get("/api/agent").json() == {
        "model": None,
        "running": False,
        "mode": None,
        "claim_id": None,
    }


def test_run_claim(client, fake_process):
    response = client.post("/api/agent/claims/CLM-1001", json=ON_A_MODEL)
    assert response.status_code == 200
    assert response.json() == {
        "model": MODEL,
        "running": True,
        "mode": "claim",
        "claim_id": None,
    }
    assert fake_process[0].arguments == ["CLM-1001", "--model", SPEC]
    start(client, "CLM-1001")
    assert client.get("/api/agent").json()["claim_id"] == "CLM-1001"


def test_one_run_at_a_time(client):
    client.post("/api/agent/claims/CLM-1001", json=ON_A_MODEL)
    for path, body in [
        ("/api/agent/claims/CLM-1002", ON_A_MODEL),
        ("/api/agent/queue", QUEUE),
    ]:
        response = client.post(path, json=body)
        assert response.status_code == 409
        assert response.json()["detail"] == "The agent is already running"


def test_run_needs_a_waiting_claim(client):
    start(client, "CLM-1001")
    response = client.post("/api/agent/claims/CLM-1001", json=ON_A_MODEL)
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 is in_progress, not waiting"
    assert client.post("/api/agent/claims/CLM-9999", json=ON_A_MODEL).status_code == 404


def test_run_queue(client, fake_process):
    response = client.post("/api/agent/queue", json=QUEUE)
    assert response.json() == {
        "model": MODEL,
        "running": True,
        "mode": "queue",
        "claim_id": None,
    }
    assert fake_process[0].arguments == ["--cap", "5", "--model", SPEC]


def test_run_queue_with_nothing_waiting(client):
    client.get("/api/claims")
    set_status("decided")
    response = client.post("/api/agent/queue", json=QUEUE)
    assert response.status_code == 409
    assert response.json()["detail"] == "No claims are waiting"


def test_finished_run_is_not_running(client, fake_process):
    client.post("/api/agent/queue", json=QUEUE)
    fake_process[0].alive = False
    assert client.get("/api/agent").json()["running"] is False
    assert client.post("/api/agent/claims/CLM-1001", json=ON_A_MODEL).status_code == 200


def test_stop(client, fake_process):
    client.post("/api/agent/claims/CLM-1001", json=ON_A_MODEL)
    start(client, "CLM-1001")
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
    assert response.json() == {
        "model": None,
        "running": False,
        "mode": None,
        "claim_id": None,
    }
    assert fake_process[0].alive is False
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "waiting"
    assert claim["decisions"] == []
    assert len(client.get("/api/claims/CLM-1001/steps").json()) == 1


def test_stop_keeps_decided_claims(client):
    start(client, "CLM-1002")
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


def test_a_run_returns_claims_left_in_progress(client):
    start(client, "CLM-1004")
    client.post("/api/agent/queue", json=QUEUE)
    assert client.get("/api/claims/CLM-1004").json()["status"] == "waiting"
    start(client, "CLM-1001")
    assert client.get("/api/agent").json()["claim_id"] == "CLM-1001"


def test_stop_marks_the_run_stopped(client, fake_process):
    start(client, "CLM-1001")
    client.post("/api/agent/stop")
    run = client.get("/api/runs/latest").json()
    assert run["status"] == "stopped"
    assert run["finished_at"] is not None
    assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting"


def test_a_model_not_allowed_is_refused(client, fake_process):
    response = client.post("/api/agent/queue", json={"model": "someone/else", "cap": 5})
    assert response.status_code == 422
    assert fake_process == []


def test_a_cap_below_one_is_refused(client):
    assert client.post("/api/agent/queue", json=QUEUE | {"cap": 0}).status_code == 422


def test_list_models(client):
    models = client.get("/api/agent/models").json()
    assert {"spec": SPEC, "label": "Claude Haiku 5.5", "default": False} in models
    assert [m["spec"] for m in models if m["default"]] == [
        "openrouter:deepseek/deepseek-v4.1-flash"
    ]


def test_a_process_that_died_leaves_nothing_in_progress(client, fake_process):
    client.post("/api/agent/claims/CLM-1001", json=ON_A_MODEL)
    start(client, "CLM-1001")
    fake_process[0].alive = False
    assert client.get("/api/agent").json()["running"] is False
    assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting"
    assert client.get("/api/runs/latest").json()["status"] == "stopped"


def test_the_agent_starts_once_the_queue_is_put_back(client, monkeypatch):
    """The agent's process finds what the request committed: the claim an earlier
    run left in progress back in the queue."""
    start(client, "CLM-1001")
    seen = []

    def start_and_look(arguments):
        seen.append(client.get("/api/claims/CLM-1001").json()["status"])
        return FakeProcess(arguments)

    monkeypatch.setattr(runner, "start_process", start_and_look)
    client.post("/api/agent/queue", json=QUEUE)
    assert seen == ["waiting"]
