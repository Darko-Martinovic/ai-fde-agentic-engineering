"""Work that survives a restart: a claim the agent was stopped on carries on
from its last saved step, on the same thread and attempt. The tests stop the
agent with KeyboardInterrupt, which the harness doesn't catch, so the claim is
left as a crash leaves it."""

import pytest
from langchain_core.messages import AIMessage, ToolMessage

import agent.__main__ as cli
from agent import api, harness, queue_agent
from agent.tests.stub import (
    FREE,
    REASONS,
    StubModel,
    call,
    calls,
    decide,
    stub,
    tool_call,
)


class StopsAfter(StubModel):
    """A stub model that gives its replies, then stops the agent as Ctrl-C would."""

    def _generate(self, *args, **kwargs):
        try:
            return super()._generate(*args, **kwargs)
        except (StopIteration, RuntimeError) as exhausted:
            raise KeyboardInterrupt from exhausted


def stopped_partway(run, saver, claim_id="CLM-1001", *replies):
    """Work a claim until the agent is stopped after these replies."""
    with pytest.raises(KeyboardInterrupt):
        harness.work_claim(
            claim_id, run, FREE, saver, StopsAfter(messages=iter(replies))
        )


def claim(backend, claim_id="CLM-1001"):
    return backend.get(f"/api/claims/{claim_id}").json()


def test_a_claim_stopped_partway_carries_on_from_its_last_step(
    backend, run, memory_saver
):
    stopped_partway(
        run,
        memory_saver,
        "CLM-1001",
        tool_call("get_claim"),
        tool_call("get_policy", policy_id="POL-2001"),
    )
    before = claim(backend)
    assert (before["status"], before["attempts"]) == ("in_progress", 1)
    seen = []

    class Reading(StubModel):
        def _generate(self, messages, *args, **kwargs):
            seen.append(messages)
            return super()._generate(messages, *args, **kwargs)

    llm = Reading(messages=iter([decide("approve", 420.0)]))
    report = harness.carry_on("CLM-1001", run, FREE, memory_saver, llm)
    assert report == "CLM-1001: approved $420.00, paid"
    after = claim(backend)
    assert (after["thread_id"], after["attempts"]) == (before["thread_id"], 1)
    assert len(after["decisions"]) == 1
    results = [m for m in seen[0] if isinstance(m, ToolMessage)]
    assert [m.name for m in results] == ["get_claim", "get_policy"]
    steps = backend.get("/api/claims/CLM-1001/steps").json()
    assert {s["thread_id"] for s in steps} == {before["thread_id"]}
    assert "failure" not in [s["kind"] for s in steps]


def test_stopped_after_the_decision_it_is_paid_once(
    backend, run, memory_saver, monkeypatch
):
    real = api.pay_claim

    def stop(claim_id, amount):
        raise KeyboardInterrupt

    monkeypatch.setattr(api, "pay_claim", stop)
    with pytest.raises(KeyboardInterrupt):
        harness.work_claim(
            "CLM-1001", run, FREE, memory_saver, stub(decide("approve", 420.0))
        )
    assert claim(backend)["payment"] is None
    monkeypatch.setattr(api, "pay_claim", real)
    report = harness.carry_on("CLM-1001", run, FREE, memory_saver, stub())
    assert report == "CLM-1001: approved $420.00, paid"
    assert len(claim(backend)["decisions"]) == 1


def test_stopped_after_the_payment_it_is_still_paid_once(
    backend, run, memory_saver, monkeypatch
):
    real = api.pay_claim

    def pay_then_stop(claim_id, amount):
        real(claim_id, amount)
        raise KeyboardInterrupt

    monkeypatch.setattr(api, "pay_claim", pay_then_stop)
    with pytest.raises(KeyboardInterrupt):
        harness.work_claim(
            "CLM-1001", run, FREE, memory_saver, stub(decide("approve", 420.0))
        )
    monkeypatch.setattr(api, "pay_claim", real)
    assert harness.carry_on("CLM-1001", run, FREE, memory_saver, stub()).endswith(
        "paid"
    )
    assert claim(backend)["payment"]["amount"] == 420.0


def test_a_claim_with_nothing_saved_starts_on_its_own_thread(
    backend, run, memory_saver
):
    api.start_claim("CLM-1001", run, "CLM-1001-unsaved")
    seen = []

    class Reading(StubModel):
        def _generate(self, messages, *args, **kwargs):
            seen.append(messages)
            return super()._generate(messages, *args, **kwargs)

    llm = Reading(messages=iter([decide("decline", 0)]))
    harness.carry_on("CLM-1001", run, FREE, memory_saver, llm)
    after = claim(backend)
    assert (after["thread_id"], after["attempts"]) == ("CLM-1001-unsaved", 1)
    assert after["status"] == "decided"
    assert seen[0][-1].content == "Claim CLM-1001"


def test_the_limit_of_model_calls_holds_across_a_restart(backend, run, memory_saver):
    stopped_partway(
        run, memory_saver, "CLM-1001", *(tool_call("get_claim") for _ in range(20))
    )
    forever = StubModel(messages=(tool_call("get_claim") for _ in range(40)))
    report = harness.carry_on("CLM-1001", run, FREE, memory_saver, forever)
    assert "TooManyModelCalls" in report
    assert backend.get("/api/runs/latest").json()["usage"]["model_calls"] == 30


def test_an_error_while_carrying_on_starts_the_claim_afresh(backend, run, memory_saver):
    stopped_partway(run, memory_saver, "CLM-1001", tool_call("get_claim"))
    first = claim(backend)["thread_id"]

    class Broken(StubModel):
        def _generate(self, *args, **kwargs):
            raise TimeoutError("the provider timed out")

    report = harness.carry_on(
        "CLM-1001", run, FREE, memory_saver, Broken(messages=iter([]))
    )
    assert report.startswith("CLM-1001: failed, back in the queue")
    harness.work_claim("CLM-1001", run, FREE, memory_saver, stub(decide("decline", 0)))
    after = claim(backend)
    assert after["attempts"] == 2
    assert after["thread_id"] != first


def test_a_queue_run_carries_on_first_outside_its_cap(
    backend, run, memory_saver, capsys
):
    stopped_partway(run, memory_saver, "CLM-1001", tool_call("get_claim"))
    harness.work_claim(
        "CLM-1003", run, FREE, memory_saver, stub(decide("approve", 3750.0))
    )
    body = {"handler_id": "HND-01", "approved": True, "note": ""}
    backend.post("/api/claims/CLM-1003/review", json=body)
    capsys.readouterr()
    queue = stub(
        calls(call("work_claim", claim_id="CLM-1005")),
        AIMessage(content="Worked CLM-1005."),
    )
    claims = stub(decide("approve", 420.0), decide("decline", 0))
    summary = queue_agent.run_queue(1, FREE, memory_saver, queue, claims)
    printed = capsys.readouterr().out.splitlines()
    assert printed[:2] == [
        "CLM-1001: approved $420.00, paid",
        "CLM-1003: approved $3,750.00, paid",
    ]
    latest = backend.get("/api/runs/latest").json()
    assert latest["claims_started"] == ["CLM-1005"]
    assert latest["summary"].startswith("CLM-1001: approved $420.00, paid\n")
    assert summary == "Worked CLM-1005."
    assert claim(backend, "CLM-1005")["status"] == "decided"


def test_a_stopped_run_is_finished_by_the_next(backend, run, monkeypatch):
    """`run` is still running, as a run whose process was killed is."""
    monkeypatch.setattr(cli, "run_queue", lambda cap, model, saver: "Done.")
    cli.main(["--cap", "1"])
    stopped = api.get_latest_run()
    assert stopped is not None
    assert (stopped["run_id"], stopped["status"]) == (run, "finished")
    assert stopped["summary"] == harness.STOPPED_RUN


def test_with_nothing_waiting_a_claim_in_progress_is_still_carried_on(
    backend, run, memory_saver, monkeypatch, capsys
):
    stopped_partway(run, memory_saver, "CLM-1001", tool_call("get_claim"))
    for listed in api.list_claims():
        if listed["claim_id"] != "CLM-1001":
            backend.post(
                f"/api/claims/{listed['claim_id']}/start",
                json={"run_id": run, "thread_id": f"{listed['claim_id']}-x"},
            )
            backend.post(
                f"/api/claims/{listed['claim_id']}/decision",
                json={
                    "decision": "decline",
                    "payout": 0,
                    "reasons": "Set up.",
                    "policy_section": "Section 9",
                },
            )
    thread_id = claim(backend)["thread_id"]
    monkeypatch.setattr(harness, "chat_model", lambda model: stub(decide("decline", 0)))
    capsys.readouterr()
    cli.main([])
    assert (claim(backend)["thread_id"], claim(backend)["attempts"]) == (thread_id, 1)
    assert capsys.readouterr().out.splitlines() == [
        f"CLM-1001: declined, because: {REASONS}",
        "No claims are waiting.",
    ]


def test_a_claim_that_cant_be_picked_up_never_stops_a_run(backend, run, memory_saver):
    """CLM-1003's decision was made through the API, so the graph saved nothing
    to carry on: the run reports it and works the queue all the same."""
    api.start_claim("CLM-1003", run, "CLM-1003-api")
    api.decide_claim(
        "CLM-1003",
        {
            "decision": "approve",
            "payout": 3750.0,
            "reasons": "Set up through the API.",
            "policy_section": "Section 7, Emergency Medical",
        },
    )
    body = {"handler_id": "HND-01", "approved": True, "note": ""}
    backend.post("/api/claims/CLM-1003/review", json=body)
    queue = stub(
        calls(call("work_claim", claim_id="CLM-1005")),
        AIMessage(content="Worked CLM-1005."),
    )
    queue_agent.run_queue(1, FREE, memory_saver, queue, stub(decide("decline", 0)))
    latest = backend.get("/api/runs/latest").json()
    assert latest["status"] == "finished"
    assert latest["summary"].startswith("CLM-1003: not picked up (RuntimeError")
    assert claim(backend, "CLM-1005")["status"] == "decided"
