"""The agent's service, picking claims back up after a handler's review, with a
stub model and its progress saved in memory."""

import threading

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from agent import api, dispatcher, graph, harness, service
from agent.tests.stub import FREE, ByClaim, StubModel, decide, stub
from backend.tests.direct_changes import set_status
from backend.tests.new_versions import GEMINI, add_version
from backend.tests.sign_ins import DANA, headers

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
    body = {"approved": approved, "note": note}
    return backend.post("/api/claims/CLM-1003/review", json=body, headers=headers(DANA))


def test_health(agent_service):
    client, _ = agent_service
    assert client.get("/api/health").json() == {"status": "ok"}


def test_after_a_sign_off_the_agent_finishes_and_pays_nothing(
    backend, run, memory_saver, agent_service, monkeypatch
):
    client, replies = agent_service
    held(backend, run, memory_saver)
    review(backend, approved=True)
    replies["llm"] = StubModel(messages=iter([]))  # never called: the work is done
    paid = []
    monkeypatch.setattr(graph.api, "pay_claim", lambda *payment: paid.append(payment))
    assert client.post("/api/claims/CLM-1003/resume").status_code == 202
    assert paid == []
    claim = backend.get("/api/claims/CLM-1003").json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 3750.0
    assert claim["payment"]["authorized_by"] == "HND-01"
    assert claim["attempts"] == 1
    finished = harness.claim_graph(FREE, memory_saver, StubModel(messages=iter([])))
    thread: RunnableConfig = {"configurable": {"thread_id": claim["thread_id"]}}
    assert finished.get_state(thread).next == ()


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
    # The sign-off paid it; the agent had nothing to finish
    assert backend.get("/api/claims/CLM-1003").json()["payment"]["amount"] == 3750.0


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
    started = client.post("/api/dispatches", json={"agents": 2})
    assert started.status_code == 202
    assert started.json() == {"agents": 2}
    run = backend.get("/api/dispatches/latest").json()
    assert (run["agents"], run["version"], run["model"], run["reasoning_effort"]) == (
        2,
        1,
        "openai/gpt-6-luna",
        "low",
    )
    assert run["status"] == "finished"
    assert [c["status"] for c in run["claims"]] == ["decided", "decided"]
    assert not service.RUNNING.locked()


def test_a_dispatch_builds_its_claim_agents_from_the_current_version(
    backend, agent_service, monkeypatch
):
    """With version 2 current on another model, the dispatch records it and its
    claim agents get its instructions and its model."""
    client, _ = agent_service
    add_version("# Version two\n\nDecide carefully.")
    declines(monkeypatch, "CLM-1005")
    built, prompts = [], []
    llm, real = harness.chat_model, harness.instructions

    def chat_model(model):
        built.append(model)
        return llm(model)

    def instructions(version):
        prompts.append(real(version))
        return prompts[-1]

    create_dispatch = api.create_dispatch

    def then_version_three(agents):
        """Version 3 is kept once the dispatch has recorded version 2."""
        run = create_dispatch(agents)
        add_version("# Version three", "deepseek/deepseek-v4.1-flash", "low")
        return run

    monkeypatch.setattr(harness, "chat_model", chat_model)
    monkeypatch.setattr(harness, "instructions", instructions)
    monkeypatch.setattr(api, "create_dispatch", then_version_three)
    client.post("/api/dispatches", json={"agents": 1})
    run = backend.get("/api/dispatches/latest").json()
    assert (run["version"], run["model"], run["reasoning_effort"]) == (
        2,
        GEMINI,
        "minimal",
    )
    assert [(m.name, m.options) for m in built] == [
        (GEMINI, {"reasoning_effort": "minimal"})
    ]
    assert prompts[0].startswith("# Version two")


def test_a_second_start_is_refused_while_one_runs(backend, agent_service):
    client, _ = agent_service
    with service.RUNNING.held("An evaluation is running"):
        refused = client.post("/api/dispatches", json={"agents": 3})
    assert refused.status_code == 409
    assert refused.json()["detail"] == "An evaluation is running"
    assert backend.get("/api/dispatches/latest").json() is None


@pytest.mark.parametrize(
    "body",
    [
        {"agents": 0},
        {"agents": 26},
    ],
)
def test_a_start_needs_one_to_25_agents(agent_service, body):
    client, _ = agent_service
    assert client.post("/api/dispatches", json=body).status_code == 422


def test_a_dispatcher_that_fails_stops_its_run_and_frees_the_next_start(
    backend, agent_service, monkeypatch
):
    client, _ = agent_service

    def broken(run, work, resuming, stop):
        raise RuntimeError("the backend went away")

    monkeypatch.setattr(dispatcher, "work_run", broken)
    client.post("/api/dispatches", json={"agents": 3})
    assert backend.get("/api/dispatches/latest").json()["status"] == "stopped"
    assert not service.RUNNING.locked()


def test_stop_asks_the_running_dispatch_to_stop(agent_service):
    client, _ = agent_service
    assert client.post("/api/runs/stop").status_code == 409
    with service.RUNNING.held("A dispatch is running"):
        stopping = client.post("/api/runs/stop")
    assert stopping.status_code == 202
    assert service.STOP.is_set()
    service.STOP.clear()


def test_starting_the_service_stops_a_run_left_running(backend):
    run = api.create_dispatch(3)
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
    client.post("/api/dispatches", json={"agents": 1})
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


TINY = ["CLM-1007", "CLM-1015", "CLM-1017", "CLM-1020", "CLM-1021"]


def copies_decide(monkeypatch, scripts):
    """Claim agents working copies, each from the script of the claim it copies."""
    llm = ByClaim(
        messages=iter([]),
        scripts={
            f"{claim_id}-E1": iter(replies) for claim_id, replies in scripts.items()
        },
    )
    monkeypatch.setattr(harness, "chat_model", lambda chosen: llm)


def test_an_evaluation_works_copies_and_leaves_the_queue_alone(
    backend, agent_service, monkeypatch, memory_saver
):
    client, _ = agent_service
    queue = backend.get("/api/claims").json()
    copies_decide(
        monkeypatch,
        {
            "CLM-1007": [decide("approve", 50.0)],
            "CLM-1015": [decide("approve", 300.0)],
            "CLM-1017": [decide("decline", 0)],
            "CLM-1020": [decide("approve", 1240.0)],
            "CLM-1021": [AIMessage(content="Hmm."), AIMessage(content="Hmm.")],
        },
    )
    body = {"evaluation_set": "evaluation", "tiny": True, "agents": 5}
    started = client.post("/api/evaluations", json=body)
    assert started.status_code == 202
    assert backend.get("/api/claims").json() == queue
    [listed] = backend.get("/api/evaluations").json()
    evaluation = backend.get(f"/api/evaluations/{listed['run_id']}").json()
    assert evaluation["status"] == "finished"
    assert [c["copy_of"] for c in evaluation["claims"]] == sorted(
        TINY, key=lambda c: next(q["submitted_on"] for q in queue if q["claim_id"] == c)
    )
    held = backend.get("/api/claims/CLM-1020-E1").json()
    assert held["status"] == "awaiting_sign_off"
    saved = {"configurable": {"thread_id": held["thread_id"]}}
    assert memory_saver.get_tuple(saved) is None
    assert evaluation["measures"]["decision_accuracy"] == pytest.approx(0.4)
    assert evaluation["measures"]["accuracy"] == pytest.approx(0.2)
    assert evaluation["measures"]["cost_of_mistakes"] == pytest.approx(2850)
    assert evaluation["measures"]["straight_through"] == pytest.approx(0.8)
    assert evaluation["measures"]["model_cost_per_claim"] == 0
    # Stub models answer at once; five claims at a time share SQLite's one
    # writer, and each claim's security check adds three calls to the backend
    assert evaluation["measures"]["seconds_per_claim"] < 2
    assert evaluation["measures"]["run_seconds"] < 30
    left = backend.get("/api/claims/CLM-1021-E1").json()
    assert left["status"] == "left_for_handler"


def test_a_dispatch_after_an_evaluation_leaves_its_copies_alone(
    backend, agent_service, monkeypatch
):
    client, _ = agent_service
    copies_decide(monkeypatch, {})
    run = api.create_evaluation("held_out", True, 5)
    api.start_claim("CLM-1104-E1", run["run_id"], "CLM-1104-E1-left")
    api.finish_run(run["run_id"], True)
    declines(monkeypatch, "CLM-1005")
    client.post("/api/dispatches", json={"agents": 3})
    dispatch = backend.get("/api/dispatches/latest").json()
    assert [c["claim_id"] for c in dispatch["claims"]] == ["CLM-1005"]
    assert backend.get("/api/claims/CLM-1104-E1").json()["status"] == "in_progress"


def test_one_run_at_a_time_whichever_kind(agent_service):
    client, _ = agent_service
    evaluation = {
        "evaluation_set": "held_out",
        "tiny": True,
        "agents": 5,
    }
    with service.RUNNING.held("A dispatch is running"):
        assert client.post("/api/evaluations", json=evaluation).status_code == 409
        dispatch = {"agents": 3}
        assert client.post("/api/dispatches", json=dispatch).status_code == 409


def test_a_resume_carries_the_claim_on_as_the_current_version(
    backend, monkeypatch, memory_saver
):
    add_version("# Version two")
    seen = []

    def carry_on(claim_id, run_id, version, saver):
        seen.append((claim_id, run_id, version.number))
        return "carried on"

    monkeypatch.setattr(harness, "carry_on", carry_on)
    assert service.carrier(lambda: memory_saver)("CLM-1003") == "carried on"
    assert seen == [("CLM-1003", None, 2)]
