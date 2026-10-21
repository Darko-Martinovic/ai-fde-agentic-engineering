from backend.tests.claim_starts import a_run, start

RUN = {"mode": "queue", "cap": 5, "model": "anthropic:claude-haiku-5-5"}


def test_no_run_yet(client):
    assert client.get("/api/runs/latest").json() is None


def test_start_a_run(client):
    run = client.post("/api/runs", json=RUN).json()
    assert run["status"] == "running"
    assert run["cap"] == 5
    assert run["todos"] == []
    assert run["claims_started"] == 0
    assert run["usage"] == {
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost": 0,
        "seconds": 0,
    }
    assert client.get("/api/runs/latest").json()["run_id"] == run["run_id"]


def test_a_cap_below_one_is_refused(client):
    assert client.post("/api/runs", json=RUN | {"cap": 0}).status_code == 422


def test_write_the_todo_list(client):
    run_id = client.post("/api/runs", json=RUN).json()["run_id"]
    todos = [
        {"content": "Work CLM-1001", "status": "completed"},
        {"content": "Work CLM-1002", "status": "in_progress"},
        {"content": "Work CLM-1003", "status": "left_for_handler"},
    ]
    response = client.put(f"/api/runs/{run_id}/todos", json={"todos": todos})
    assert response.json()["todos"] == todos
    bad = [{"content": "Work CLM-1004", "status": "maybe"}]
    assert (
        client.put(f"/api/runs/{run_id}/todos", json={"todos": bad}).status_code == 422
    )


def test_finish_a_run(client):
    run_id = client.post("/api/runs", json=RUN).json()["run_id"]
    run = client.post(
        f"/api/runs/{run_id}/finish", json={"summary": "Worked 5."}
    ).json()
    assert run["status"] == "finished"
    assert run["summary"] == "Worked 5."
    assert run["finished_at"] is not None
    again = client.post(f"/api/runs/{run_id}/finish", json={"summary": "Again."})
    assert again.status_code == 409
    todos = client.put(f"/api/runs/{run_id}/todos", json={"todos": []})
    assert todos.status_code == 409


def test_usage_adds_up_by_run(client):
    first = client.post("/api/runs", json=RUN).json()["run_id"]
    call = {
        "claim_id": "CLM-1001",
        "model": "anthropic:claude-haiku-5-5",
        "input_tokens": 1000,
        "output_tokens": 200,
        "cost": 0.0002,
        "seconds": 1.5,
    }
    client.post(f"/api/runs/{first}/usage", json=call)
    run = client.post(f"/api/runs/{first}/usage", json=call | {"claim_id": None}).json()
    assert run["usage"]["model_calls"] == 2
    assert run["usage"]["input_tokens"] == 2000
    assert run["usage"]["seconds"] == 3
    second = client.post("/api/runs", json=RUN).json()
    assert second["usage"]["model_calls"] == 0


def test_an_unknown_run(client):
    assert client.post("/api/runs/99/finish", json={"summary": "x"}).status_code == 404


def test_claims_started_count_once(client):
    run_id = a_run(client)
    start(client, "CLM-1001", run_id)
    start(client, "CLM-1002", run_id)
    run = client.get("/api/runs/latest").json()
    assert run["claims_started"] == 2
