"""The agent's service, picking claims back up after a handler's review, with a
stub model and its progress saved in memory."""

import threading

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

from agent import api, dispatcher, harness, service
from agent.tests.stub import FREE, ByClaim, StubModel, decide, stub
from backend.tests.direct_changes import set_status

NOTE = "The bill is $3,800.00, less the $100.00 the clinic waived."


@pytest.fixture
def agent_service(memory_saver, monkeypatch):
    """The service without its lifespan, carrying claims on with `llm`, whose
    replies each test gives, and the tests' saver. Its background work runs
    before each request returns, so a test sees what it did."""
    monkeypatch.setattr(service, "in_background", lambda work, *args: work(*args))
    replies = {"llm": stub()}
    service.app.dependency_overrides[service.carrier] = lambda: (
        lambda claim_id: harness.carry_on(
            claim_id, None, FREE, memory_saver, replies["llm"]
        )
    )
    service.app.dependency_overrides[service.savers] = lambda: lambda: memory_saver
    yield TestClient(service.app), replies
    service.app.dependency_overrides.clear()


def held(backend, run, memory_saver, payout=3750.0):
    """CLM-1003 approved for `payout` and waiting for a sign-off."""
    harness.work_claim(
        "CLM-1003", run, FREE, memory_saver, stub(decide("approve", payout))
    )
    assert backend.get("/api/claims/CLM-1003").json()["status"] == "awaiting_sign_off"


def review(backend, approved, note=""):
    body = {"handler_id": "HND-01", "approved": approved, "note": note}
    return backend.post("/api/claims/CLM-1003/review", json=body)


def test_health(agent_service):
    client, _ = agent_service
    assert client.get("/api/health").json() == {"status": "ok"}


def test_a_sign_off_is_picked_up_and_paid_once(
    backend, run, memory_saver, agent_service
):
    client, replies = agent_service
    held(backend, run, memory_saver)
    review(backend, approved=True)
    replies["llm"] = StubModel(messages=iter([]))  # never called: paying needs no model
    assert client.post("/api/claims/CLM-1003/resume").status_code == 202
    claim = backend.get("/api/claims/CLM-1003").json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 3750.0
    assert claim["payment"]["authorized_by"] == "HND-01"
    assert claim["attempts"] == 1
    again = client.post("/api/claims/CLM-1003/resume")
    assert again.status_code == 409
    assert backend.get("/api/claims/CLM-1003").json()["payment"]["amount"] == 3750.0


def test_a_claim_still_waiting_for_its_review_isnt_picked_up(
    backend, run, memory_saver, agent_service
):
    client, _ = agent_service
    held(backend, run, memory_saver)
    assert client.post("/api/claims/CLM-1003/resume").status_code == 409
    assert backend.get("/api/claims/CLM-1003").json()["status"] == "awaiting_sign_off"


def test_an_unknown_claim_isnt_found(agent_service):
    client, _ = agent_service
    assert client.post("/api/claims/CLM-9999/resume").status_code == 404


def test_a_rejection_goes_back_to_the_agent_with_the_note(
    backend, run, memory_saver, agent_service
):
    client, replies = agent_service
    held(backend, run, memory_saver)
    review(backend, approved=False, note=NOTE)
    seen = []

    class Reading(StubModel):
        def _generate(self, messages, *args, **kwargs):
            seen.append(messages)
            return super()._generate(messages, *args, **kwargs)

    replies["llm"] = Reading(messages=iter([decide("approve", 3700.0)]))
    assert client.post("/api/claims/CLM-1003/resume").status_code == 202
    [prompt] = seen
    assert isinstance(prompt[-1], HumanMessage)
    assert prompt[-1].content == f"A handler rejected the payout: {NOTE}"
    claim = backend.get("/api/claims/CLM-1003").json()
    assert claim["status"] == "awaiting_sign_off"
    assert [d["payout"] for d in claim["decisions"]] == [3750.0, 3700.0]
    assert claim["payment"] is None

    review(backend, approved=True)
    replies["llm"] = StubModel(messages=iter([]))
    client.post("/api/claims/CLM-1003/resume")
    paid = backend.get("/api/claims/CLM-1003").json()
    assert (paid["status"], paid["payment"]["amount"]) == ("decided", 3700.0)


def test_an_agent_that_answers_a_rejection_without_deciding_leaves_it_for_a_handler(
    backend, run, memory_saver, agent_service
):
    client, replies = agent_service
    held(backend, run, memory_saver)
    review(backend, approved=False, note=NOTE)
    replies["llm"] = stub(AIMessage(content="The payout stays at $3,750.00."))
    client.post("/api/claims/CLM-1003/resume")
    claim = backend.get("/api/claims/CLM-1003").json()
    assert claim["status"] == "left_for_handler"
    assert len(claim["decisions"]) == 1


def test_a_decision_the_graph_never_saved_isnt_worked_again(
    backend, run, agent_service, capsys
):
    """As when a decision is made through the API: the service says it can't
    pick the claim up, and the model isn't called."""
    client, replies = agent_service
    backend.post(
        "/api/claims/CLM-1003/start", json={"run_id": run, "thread_id": "CLM-1003-api"}
    )
    backend.post(
        "/api/claims/CLM-1003/decision",
        json={
            "decision": "approve",
            "payout": 3750.0,
            "reasons": "Set up through the API.",
            "policy_section": "Section 7, Emergency Medical",
        },
    )
    review(backend, approved=True)
    replies["llm"] = StubModel(messages=iter([]))
    assert client.post("/api/claims/CLM-1003/resume").status_code == 202
    assert "CLM-1003: not picked up (RuntimeError" in capsys.readouterr().out
    assert backend.get("/api/claims/CLM-1003").json()["payment"] is None


def declines(monkeypatch, *claim_ids):
    """Every other claim decided already, and claim agents that decline these."""
    claims = [c["claim_id"] for c in api.list_claims()]
    set_status("decided", *(c for c in claims if c not in claim_ids))
    llm = ByClaim(
        messages=iter([]),
        scripts={claim_id: iter([decide("decline", 0)]) for claim_id in claim_ids},
    )
    monkeypatch.setattr(harness, "chat_model", lambda chosen: llm)


def test_a_dispatch_starts_at_once_and_works_the_queue(
    backend, agent_service, monkeypatch
):
    client, _ = agent_service
    declines(monkeypatch, "CLM-1004", "CLM-1005")
    started = client.post("/api/dispatches", json={"agents": 2, "model": FREE.spec})
    assert started.status_code == 202
    assert started.json() == {"agents": 2, "model": FREE.spec}
    run = backend.get("/api/dispatches/latest").json()
    assert (run["agents"], run["model"], run["reasoning_effort"]) == (
        2,
        FREE.spec,
        "none",
    )
    assert run["status"] == "finished"
    assert [c["status"] for c in run["claims"]] == ["decided", "decided"]
    assert not service.RUNNING.locked()


def test_a_dispatch_records_the_models_reasoning_effort(
    backend, agent_service, monkeypatch
):
    client, _ = agent_service
    declines(monkeypatch, "CLM-1005")
    luna = "openrouter:openai/gpt-6-luna"
    client.post("/api/dispatches", json={"agents": 1, "model": luna})
    run = backend.get("/api/dispatches/latest").json()
    assert (run["model"], run["reasoning_effort"]) == (luna, "low")


def test_a_second_start_is_refused_while_one_runs(backend, agent_service):
    client, _ = agent_service
    with service.RUNNING:
        refused = client.post("/api/dispatches", json={"agents": 3, "model": FREE.spec})
    assert refused.status_code == 409
    assert refused.json()["detail"] == "A dispatch or an evaluation is already running"
    assert backend.get("/api/dispatches/latest").json() is None


@pytest.mark.parametrize(
    "body",
    [
        {"agents": 0, "model": FREE.spec},
        {"agents": 26, "model": FREE.spec},
        {"agents": 3, "model": "someone/else"},
    ],
)
def test_a_start_needs_one_to_25_agents_and_a_model_allowed(agent_service, body):
    client, _ = agent_service
    assert client.post("/api/dispatches", json=body).status_code == 422


def test_a_dispatcher_that_fails_stops_its_run_and_frees_the_next_start(
    backend, agent_service, monkeypatch
):
    client, _ = agent_service

    def broken(run, work, resuming, stop):
        raise RuntimeError("the backend went away")

    monkeypatch.setattr(dispatcher, "work_run", broken)
    client.post("/api/dispatches", json={"agents": 3, "model": FREE.spec})
    assert backend.get("/api/dispatches/latest").json()["status"] == "stopped"
    assert not service.RUNNING.locked()


def test_stop_asks_the_running_dispatch_to_stop(agent_service):
    client, _ = agent_service
    assert client.post("/api/runs/stop").status_code == 409
    with service.RUNNING:
        stopping = client.post("/api/runs/stop")
    assert stopping.status_code == 202
    assert service.STOP.is_set()
    service.STOP.clear()


def test_starting_the_service_stops_a_run_left_running(backend):
    run = api.create_dispatch(3, FREE.spec, "none")
    with TestClient(service.app):
        pass
    assert backend.get("/api/dispatches/latest").json()["run_id"] == run["run_id"]
    assert backend.get("/api/dispatches/latest").json()["status"] == "stopped"


def test_a_claim_being_carried_on_is_kept_from_dispatches(
    backend, run, memory_saver, agent_service
):
    client, _ = agent_service
    held(backend, run, memory_saver)
    review(backend, approved=True)
    during = []

    def carry(claim_id):
        during.append(set(service.RESUMING))
        return f"{claim_id}: carried on"

    service.app.dependency_overrides[service.carrier] = lambda: carry
    client.post("/api/claims/CLM-1003/resume")
    assert during == [{"CLM-1003"}]
    assert set() == service.RESUMING


def test_background_work_runs_on_a_thread_of_its_own():
    done = threading.Event()
    service.in_background(lambda caller: done.set(), threading.get_ident())
    assert done.wait(timeout=5)


def test_a_start_clears_an_earlier_stop(backend, agent_service, monkeypatch):
    client, _ = agent_service
    declines(monkeypatch, "CLM-1005")
    service.STOP.set()
    client.post("/api/dispatches", json={"agents": 1, "model": FREE.spec})
    run = backend.get("/api/dispatches/latest").json()
    assert run["status"] == "finished"
    assert run["claims"][0]["status"] == "decided"


def test_a_claim_already_being_picked_up_is_refused(
    backend, run, memory_saver, agent_service
):
    client, _ = agent_service
    held(backend, run, memory_saver)
    review(backend, approved=True)
    service.RESUMING.add("CLM-1003")
    try:
        again = client.post("/api/claims/CLM-1003/resume")
    finally:
        service.RESUMING.discard("CLM-1003")
    assert again.status_code == 409
    assert again.json()["detail"] == "Claim CLM-1003 is being picked up already"
