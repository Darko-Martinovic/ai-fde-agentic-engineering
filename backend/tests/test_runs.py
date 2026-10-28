import pytest

from backend.tests.claim_starts import DISPATCH, a_run, start
from backend.tests.workflow_steps import approved, decide, fail, pay, referred, review

SPELL = {"thread_id": "t", "seconds": 12.5}
CALL = {
    "thread_id": "t",
    "model": "test",
    "input_tokens": 1200,
    "output_tokens": 300,
    "cost": 0.0042,
    "seconds": 1.5,
}


def create(client, **changes):
    return client.post("/api/runs/dispatches", json=DISPATCH | changes)


def test_no_dispatch_yet(client):
    assert client.get("/api/dispatches/latest").json() is None


def test_a_dispatch_starts_running_with_its_n_and_model(client):
    run = create(client, agents=7, model="openrouter:openai/gpt-6-luna").json()
    assert (run["kind"], run["status"], run["agents"]) == ("dispatch", "running", 7)
    assert (run["model"], run["reasoning_effort"]) == (
        "openrouter:openai/gpt-6-luna",
        "none",
    )
    assert (run["claims"], run["summary"], run["seconds"]) == ([], None, None)
    assert run["usage"] == {
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost": 0,
    }
    assert client.get("/api/dispatches/latest").json()["run_id"] == run["run_id"]


@pytest.mark.parametrize("agents", [0, 26])
def test_a_dispatch_has_one_to_25_agents(client, agents):
    assert create(client, agents=agents).status_code == 422


def test_a_dispatchs_claims_keep_their_order_and_show_their_work(client):
    run_id = a_run(client)
    listed = ["CLM-1004", "CLM-1001", "CLM-1002"]
    response = client.put(f"/api/runs/{run_id}/claims", json={"claim_ids": listed})
    assert [c["claim_id"] for c in response.json()["claims"]] == listed
    start(client, "CLM-1004", run_id)
    client.post("/api/claims/CLM-1004/model-calls", json=CALL | {"run_id": run_id})
    client.post("/api/claims/CLM-1004/work-times", json=SPELL | {"run_id": run_id})
    client.post("/api/claims/CLM-1004/work-times", json=SPELL | {"run_id": None})
    run = client.get("/api/dispatches/latest").json()
    first, second, _ = run["claims"]
    assert (first["status"], first["seconds"], first["model_cost"]) == (
        "in_progress",
        12.5,
        0.0042,
    )
    assert first["started_at"] is not None
    assert first["customer_name"]
    assert (second["status"], second["started_at"], second["seconds"]) == (
        "waiting",
        None,
        0,
    )
    assert run["usage"]["model_calls"] == 1


def test_a_dispatchs_claims_must_be_known_and_it_must_be_running(client):
    run_id = a_run(client)
    unknown = client.put(f"/api/runs/{run_id}/claims", json={"claim_ids": ["CLM-9999"]})
    assert unknown.status_code == 404
    client.post(f"/api/runs/{run_id}/finish", json={"stopped": False})
    late = client.put(f"/api/runs/{run_id}/claims", json={"claim_ids": ["CLM-1001"]})
    assert late.status_code == 409


def worked_every_way(client, run_id):
    """Claims left in every state a dispatch can leave them in."""
    approved(client, "CLM-1001", 420.0)
    pay(client, "CLM-1001", 420.0)
    start(client, "CLM-1005")
    decide(client, "CLM-1005", "decline", 0)
    referred(client, "CLM-1010")
    approved(client, "CLM-1008", 2240.0)
    for _ in range(2):
        start(client, "CLM-1012")
        fail(client, "CLM-1012")
    start(client, "CLM-1004")
    approved(client, "CLM-1003", 3750.0)
    review(client, "CLM-1003")
    approved(client, "CLM-1011", 1150.0)
    review(client, "CLM-1011", approved=False, note="Too much.")
    order = [
        "CLM-1001",
        "CLM-1005",
        "CLM-1010",
        "CLM-1008",
        "CLM-1012",
        "CLM-1004",
        "CLM-1003",
        "CLM-1011",
        "CLM-1013",
    ]
    client.put(f"/api/runs/{run_id}/claims", json={"claim_ids": order})


def test_finishing_builds_the_summary_from_the_records(client):
    run_id = a_run(client)
    worked_every_way(client, run_id)
    run = client.post(f"/api/runs/{run_id}/finish", json={"stopped": False}).json()
    assert run["status"] == "finished"
    assert run["finished_at"] is not None
    assert run["seconds"] >= 0
    assert run["summary"] == {
        "approved": 2,
        "declined": 1,
        "referred": 1,
        "waiting_for_sign_off": [{"claim_id": "CLM-1008", "payout": 2240.0}],
        "left_for_handler": ["CLM-1012"],
        "unfinished": ["CLM-1004", "CLM-1003", "CLM-1011", "CLM-1013"],
    }
    again = client.post(f"/api/runs/{run_id}/finish", json={"stopped": False})
    assert again.status_code == 409


def test_a_dispatch_asked_to_stop_finishes_as_stopped(client):
    run_id = a_run(client)
    run = client.post(f"/api/runs/{run_id}/finish", json={"stopped": True}).json()
    assert run["status"] == "stopped"
    assert run["summary"]["unfinished"] == []


def test_stopping_runs_stops_every_running_one_and_leaves_finished_ones(client):
    finished = create(client).json()["run_id"]
    client.post(f"/api/runs/{finished}/finish", json={"stopped": False})
    first = create(client).json()["run_id"]
    second = create(client).json()["run_id"]
    assert client.post("/api/runs/stop-all").json() == {"run_ids": [first, second]}
    assert client.get("/api/dispatches/latest").json()["status"] == "stopped"
    assert client.post("/api/runs/stop-all").json() == {"run_ids": []}


def test_an_unknown_run(client):
    response = client.post("/api/runs/99/finish", json={"stopped": False})
    assert response.status_code == 404


def test_the_latest_dispatch_is_the_last_started(client):
    first = create(client).json()["run_id"]
    second = create(client).json()["run_id"]
    assert second > first
    assert client.get("/api/dispatches/latest").json()["run_id"] == second
