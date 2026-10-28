import time

import pytest
from sqlalchemy import event

from backend import db, judge
from backend.tests.judge_answers import B
from backend.tests.workflow_steps import decide

TINY = ["CLM-1104", "CLM-1106", "CLM-1110", "CLM-1112", "CLM-1114"]


def evaluation(client, tiny=True):
    body = {"evaluation_set": "held_out", "tiny": tiny, "agents": 5}
    return client.post("/api/runs/evaluations", json=body).json()["run_id"]


def decided(client, run_id, claim_ids):
    """The agent declines each of these copies."""
    for claim_id in claim_ids:
        copy_id = f"{claim_id}-E{run_id}"
        client.post(
            f"/api/claims/{copy_id}/start",
            json={"run_id": run_id, "thread_id": f"{copy_id}-t"},
        )
        decide(client, copy_id, "decline", 0)


def finish(client, run_id, stopped=False):
    return client.post(f"/api/runs/{run_id}/finish", json={"stopped": stopped})


def test_seeding_keeps_every_handlers_reason_and_reference(client, judged):
    run_id = evaluation(client)
    decided(client, run_id, TINY)
    finish(client, run_id)
    assert len(judged) == 5
    for state in judged:
        assert state["handler"]["reason"]
        assert state["handler"]["reference"]
        assert state["agent"]["decision"] == "decline"


def test_nothing_the_claim_agent_reads_holds_a_handlers_reason(client, judged):
    run_id = evaluation(client)
    decided(client, run_id, TINY)
    finish(client, run_id)
    reasons = [state["handler"]["reason"] for state in judged]
    copy_id = f"CLM-1104-E{run_id}"
    claim = client.get(f"/api/claims/{copy_id}").json()
    read = [
        client.get(f"/api/claims/{copy_id}").text,
        client.get(f"/api/policies/{claim['policy_id']}").text,
        client.get(f"/api/customers/{claim['customer_id']}").text,
        client.get("/api/versions/current").text,
    ]
    assert not any(reason in text for reason in reasons for text in read)


def test_an_undecided_copy_is_an_f_without_asking_the_judge(client, judged):
    run_id = evaluation(client)
    decided(client, run_id, TINY[:4])
    finish(client, run_id)
    assert len(judged) == 4
    copies = client.get(f"/api/evaluations/{run_id}").json()["claims"]
    undecided = next(c for c in copies if c["copy_of"] == "CLM-1114")
    assert (undecided["grade"], undecided["letter"], undecided["judge_cost"]) == (
        0,
        "F",
        0,
    )


def test_an_ungraded_copy_is_left_out_of_the_grade(client, monkeypatch):
    graded = iter([B, None, B, None, B])
    monkeypatch.setattr(judge, "grade", lambda handler, agent: next(graded))
    run_id = evaluation(client)
    decided(client, run_id, TINY)
    finish(client, run_id)
    result = client.get(f"/api/evaluations/{run_id}").json()
    assert result["measures"]["grade"] == pytest.approx(2.2)
    assert result["measures"]["judge_cost"] == pytest.approx(3 * B.cost)
    assert sum(c["grade"] is None for c in result["claims"]) == 2
    assert result["measures"]["model_cost_per_claim"] == 0


def test_with_no_copy_graded_an_evaluation_has_no_grade(client, monkeypatch):
    monkeypatch.setattr(judge, "grade", lambda handler, agent: None)
    run_id = evaluation(client)
    decided(client, run_id, TINY)
    finish(client, run_id)
    measures = client.get(f"/api/evaluations/{run_id}").json()["measures"]
    assert (measures["grade"], measures["judge_cost"]) == (None, 0)


def test_a_stopped_evaluation_isnt_graded(client, judged):
    run_id = evaluation(client)
    decided(client, run_id, TINY)
    assert finish(client, run_id, stopped=True).json()["status"] == "stopped"
    assert judged == []
    assert client.get(f"/api/evaluations/{run_id}").json()["measures"]["grade"] is None


def test_on_a_free_model_nothing_is_graded(client, judged, monkeypatch):
    run_id = evaluation(client)
    decided(client, run_id, TINY)
    monkeypatch.setenv("MODEL_NAME", "openrouter:openrouter/free")
    finish(client, run_id)
    assert judged == []


def test_a_dispatch_isnt_graded(client, judged):
    run_id = client.post("/api/runs/dispatches", json={"agents": 3}).json()["run_id"]
    finish(client, run_id)
    assert judged == []


def test_grading_is_parallel_and_holds_no_connection(client, monkeypatch):
    """25 copies with a judge that takes 0.3 seconds each finish in well under
    the time one after another would take, and no database connection is
    open while the judge answers."""
    open_connections = []
    every_checkout = []
    during = []

    @event.listens_for(db.engine(), "checkout")
    def checked_out(*args):
        open_connections.append(1)
        every_checkout.append(1)

    @event.listens_for(db.engine(), "checkin")
    def checked_in(*args):
        open_connections.pop()

    def slow(handler, agent):
        during.append(len(open_connections))
        time.sleep(0.3)
        return B

    monkeypatch.setattr(judge, "grade", slow)
    run_id = evaluation(client, tiny=False)
    copies = client.get(f"/api/evaluations/{run_id}").json()["claims"]
    decided(client, run_id, [c["copy_of"] for c in copies])
    started = time.monotonic()
    finish(client, run_id)
    assert time.monotonic() - started < 2
    assert len(during) == 25
    assert set(during) == {0}
    assert every_checkout  # the count is real: the finish did take connections
    event.remove(db.engine(), "checkout", checked_out)
    event.remove(db.engine(), "checkin", checked_in)
