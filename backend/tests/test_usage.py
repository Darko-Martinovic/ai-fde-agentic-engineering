from datetime import datetime

import pytest

from backend.tests.claim_starts import a_run, start, start_alone
from backend.tests.usage_rows import model_calls, work_times

CALL = {
    "thread_id": "CLM-1004-test",
    "model": "openrouter:openai/gpt-6-luna",
    "input_tokens": 1200,
    "output_tokens": 300,
    "cost": 0.0042,
    "seconds": 1.5,
}


def test_a_model_call_is_recorded_with_its_run(client):
    run_id = a_run(client)
    start(client, "CLM-1004", run_id)
    recorded = client.post(
        "/api/claims/CLM-1004/model-calls", json=CALL | {"run_id": run_id}
    )
    assert recorded.status_code == 200
    assert recorded.json()["claim_id"] == "CLM-1004"
    [row] = model_calls("CLM-1004")
    assert {key: row[key] for key in CALL} == CALL
    assert (row["claim_id"], row["run_id"]) == ("CLM-1004", run_id)
    assert row["recorded_at"]
    assert client.get("/api/dispatches/latest").json()["usage"]["cost"] == 0.0042


def test_a_model_call_outside_a_run_has_none(client):
    start_alone(client, "CLM-1004")
    client.post("/api/claims/CLM-1004/model-calls", json=CALL | {"run_id": None})
    [row] = model_calls("CLM-1004")
    assert row["run_id"] is None


def test_a_spell_of_work_starts_its_seconds_before_it_is_recorded(client):
    start_alone(client, "CLM-1004")
    spell = {"thread_id": "CLM-1004-test", "run_id": None, "seconds": 12.5}
    before = datetime.now().astimezone()
    recorded = client.post("/api/claims/CLM-1004/work-times", json=spell).json()
    started = datetime.fromisoformat(recorded["started_at"])
    assert (before - started).total_seconds() == pytest.approx(12.5, abs=0.5)
    [row] = work_times("CLM-1004")
    assert (row["run_id"], row["seconds"]) == (None, 12.5)


@pytest.mark.parametrize("path", ["model-calls", "work-times"])
def test_a_claim_not_started_is_refused(client, path):
    body = CALL | {"run_id": None}
    response = client.post(f"/api/claims/CLM-1004/{path}", json=body)
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1004 has not been started"


@pytest.mark.parametrize("path", ["model-calls", "work-times"])
def test_an_unknown_claim_or_run_is_not_found(client, path):
    start_alone(client, "CLM-1004")
    unknown_claim = client.post(
        f"/api/claims/CLM-9999/{path}", json=CALL | {"run_id": None}
    )
    assert unknown_claim.status_code == 404
    unknown_run = client.post(
        f"/api/claims/CLM-1004/{path}", json=CALL | {"run_id": 99}
    )
    assert unknown_run.status_code == 404
    assert unknown_run.json()["detail"] == "Run 99 not found"


@pytest.mark.parametrize(
    ("path", "field"),
    [
        ("model-calls", "input_tokens"),
        ("model-calls", "output_tokens"),
        ("model-calls", "cost"),
        ("model-calls", "seconds"),
        ("work-times", "seconds"),
    ],
)
def test_negative_numbers_are_refused(client, path, field):
    start_alone(client, "CLM-1004")
    body = CALL | {"run_id": None, field: -1}
    response = client.post(f"/api/claims/CLM-1004/{path}", json=body)
    assert response.status_code == 422
