"""The queue agent, run by harness.run_queue, on stub models."""

import pytest
from langchain_core.messages import AIMessage

from agent import harness
from agent.tests.stub import FREE, StubModel, call, calls, decide, stub


def todos(*items):
    return call("write_todos", todos=[{"content": c, "status": s} for c, s in items])


def claim_status(backend, claim_id):
    return backend.get(f"/api/claims/{claim_id}").json()["status"]


def test_a_run_writes_its_todo_list_works_claims_and_sums_up(backend):
    queue = stub(
        calls(call("list_waiting_claims")),
        calls(todos(("Work CLM-1001", "in_progress"), ("Work CLM-1005", "pending"))),
        calls(call("work_claim", claim_id="CLM-1001")),
        calls(call("work_claim", claim_id="CLM-1005")),
        calls(todos(("Work CLM-1001", "completed"), ("Work CLM-1005", "completed"))),
        AIMessage(content="Approved CLM-1001 and declined CLM-1005."),
    )
    claims = stub(
        decide("approve", 420),
        calls(call("pay_claim", amount=420)),
        AIMessage(content="Paid."),
        decide("decline", 0),
        AIMessage(content="Declined."),
    )
    summary = harness.run_queue(2, FREE, queue, claims)
    assert summary == "Approved CLM-1001 and declined CLM-1005."
    run = backend.get("/api/runs/latest").json()
    assert run["status"] == "finished"
    assert run["summary"] == summary
    assert run["claims_started"] == ["CLM-1001", "CLM-1005"]
    assert [t["status"] for t in run["todos"]] == ["completed", "completed"]
    assert claim_status(backend, "CLM-1001") == "decided"
    assert claim_status(backend, "CLM-1005") == "decided"
    assert run["usage"]["model_calls"] == 11


def test_a_claim_past_the_cap_is_refused_and_stays_waiting(backend):
    queue = stub(
        calls(call("work_claim", claim_id="CLM-1005")),
        calls(call("work_claim", claim_id="CLM-1013")),
        AIMessage(content="Worked one; the cap stopped the second."),
    )
    claims = stub(decide("decline", 0), AIMessage(content="Declined."))
    harness.run_queue(1, FREE, queue, claims)
    assert claim_status(backend, "CLM-1005") == "decided"
    assert claim_status(backend, "CLM-1013") == "waiting"
    assert backend.get("/api/runs/latest").json()["claims_started"] == ["CLM-1005"]


def test_a_failed_claim_does_not_stop_the_run_and_is_tried_again(backend):
    queue = stub(
        calls(call("work_claim", claim_id="CLM-1001")),
        calls(call("work_claim", claim_id="CLM-1005")),
        calls(call("work_claim", claim_id="CLM-1001")),
        AIMessage(content="CLM-1001 failed once, then was paid; CLM-1005 declined."),
    )
    claims = stub(
        AIMessage(content="I'm not sure."),
        decide("decline", 0),
        AIMessage(content="Declined."),
        decide("approve", 420),
        calls(call("pay_claim", amount=420)),
        AIMessage(content="Paid."),
    )
    harness.run_queue(2, FREE, queue, claims)
    assert claim_status(backend, "CLM-1001") == "decided"
    assert claim_status(backend, "CLM-1005") == "decided"
    steps = backend.get("/api/claims/CLM-1001/steps").json()
    assert [s["kind"] for s in steps].count("failure") == 1


def test_a_claim_that_fails_twice_is_left_for_a_handler(backend):
    queue = stub(
        calls(call("work_claim", claim_id="CLM-1001")),
        calls(call("work_claim", claim_id="CLM-1001")),
        AIMessage(content="CLM-1001 is left for a handler."),
    )
    claims = stub(AIMessage(content="Unsure."), AIMessage(content="Still unsure."))
    harness.run_queue(1, FREE, queue, claims)
    assert claim_status(backend, "CLM-1001") == "left_for_handler"
    assert backend.get("/api/runs/latest").json()["status"] == "finished"


def test_missed_claims_are_worked_before_the_run_finishes(backend):
    queue = stub(
        AIMessage(content="Nothing to do."),
        calls(call("work_claim", claim_id="CLM-1001")),
        AIMessage(content="Worked CLM-1001 after the reminder."),
    )
    claims = stub(
        decide("approve", 420),
        calls(call("pay_claim", amount=420)),
        AIMessage(content="Paid."),
    )
    summary = harness.run_queue(1, FREE, queue, claims)
    assert summary == "Worked CLM-1001 after the reminder."
    assert claim_status(backend, "CLM-1001") == "decided"


def test_missed_lists_retries_then_new_claims_within_the_cap(backend, run):
    harness.work_claim("CLM-1001", run, FREE, stub(AIMessage(content="Unsure.")))
    assert harness.missed(["CLM-1001"], 2) == ["CLM-1001", "CLM-1002"]
    assert harness.missed(["CLM-1001"], 1) == ["CLM-1001"]


def test_work_claim_calls_made_at_once_go_one_at_a_time_within_the_cap(backend):
    queue = stub(
        calls(
            call("work_claim", claim_id="CLM-1005"),
            call("work_claim", claim_id="CLM-1013"),
        ),
        AIMessage(content="Worked one; the cap stopped the second."),
    )
    claims = stub(decide("decline", 0), AIMessage(content="Declined."))
    harness.run_queue(1, FREE, queue, claims)
    assert claim_status(backend, "CLM-1005") == "decided"
    assert claim_status(backend, "CLM-1013") == "waiting"


def test_claims_still_missed_after_the_reminder_are_named_in_the_summary(backend):
    queue = stub(AIMessage(content="Nothing to do."), AIMessage(content="Done."))
    summary = harness.run_queue(1, FREE, queue, stub())
    assert summary == "Done.\n\n" + harness.LEFT_WAITING.format(claims="CLM-1001")


def test_a_run_that_breaks_is_finished_with_what_stopped_it(backend):
    class Broken(StubModel):
        def _generate(self, *args, **kwargs):
            raise TimeoutError("the provider timed out")

    with pytest.raises(TimeoutError):
        harness.run_queue(1, FREE, Broken(messages=iter([])), stub())
    run = backend.get("/api/runs/latest").json()
    assert run["status"] == "finished"
    assert run["summary"] == "The run stopped: TimeoutError: the provider timed out"
