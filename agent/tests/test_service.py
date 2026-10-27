"""The agent's service, picking claims back up after a handler's review, with a
stub model and its progress saved in memory."""

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

from agent import harness, service
from agent.tests.stub import FREE, StubModel, decide, stub

NOTE = "The bill is $3,800.00, less the $100.00 the clinic waived."


@pytest.fixture
def agent_service(memory_saver):
    """The service without its lifespan, carrying claims on with `llm`, whose
    replies each test gives, and the tests' saver."""
    replies = {"llm": stub()}
    service.app.dependency_overrides[service.carrier] = lambda: (
        lambda claim_id: harness.carry_on(
            claim_id, None, FREE, memory_saver, replies["llm"]
        )
    )
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
