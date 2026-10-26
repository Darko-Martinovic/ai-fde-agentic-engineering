import pytest

from backend import db
from backend.store import claims
from backend.tests.claim_starts import a_run, start
from backend.tests.workflow_steps import approved, decide, fail, pay, referred, resolve


def test_start_claim(client):
    response = start(client, "CLM-1001")
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_start_claim_twice(client):
    start(client, "CLM-1001")
    response = start(client, "CLM-1001")
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 is in_progress, not waiting"


def test_start_unknown_claim(client):
    assert start(client, "CLM-9999").status_code == 404


def test_steps_in_order(client):
    for kind, text in [
        ("tool_call", "get_claim"),
        ("tool_result", "the claim"),
        ("reply", "Approved"),
    ]:
        response = client.post(
            "/api/claims/CLM-1001/steps",
            json={"thread_id": "t-1", "kind": kind, "text": text},
        )
        assert response.status_code == 200
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [s["kind"] for s in steps] == ["tool_call", "tool_result", "reply"]
    assert [s["text"] for s in steps] == ["get_claim", "the claim", "Approved"]
    assert client.get("/api/claims/CLM-1002/steps").json() == []


def test_step_kind_is_checked(client):
    response = client.post(
        "/api/claims/CLM-1001/steps",
        json={"thread_id": "t-1", "kind": "thought", "text": "hmm"},
    )
    assert response.status_code == 422


def test_steps_for_unknown_claim(client):
    assert client.get("/api/claims/CLM-9999/steps").status_code == 404


def test_decide_needs_a_claim_in_progress(client):
    response = decide(client, "CLM-1001", "decline", 0)
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 is waiting, not in_progress"


@pytest.mark.parametrize(
    ("decision", "payout", "status"),
    [
        ("decline", 0, "decided"),
        ("refer", 0, "referred"),
        ("approve", 420, "in_progress"),
        ("approve", 1150, "awaiting_sign_off"),
    ],
)
def test_decide_claim(client, decision, payout, status):
    start(client, "CLM-1001")
    claim = decide(client, "CLM-1001", decision, payout).json()
    assert claim["status"] == status
    [recorded] = claim["decisions"]
    assert recorded["decided_by"] == "agent"
    assert recorded["decision"] == decision
    assert recorded["payout"] == payout
    assert recorded["policy_section"] == "Section 3, Trip Delay"


def test_decide_twice(client):
    approved(client, "CLM-1001", 420)
    response = decide(client, "CLM-1001", "decline", 0)
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 already has a decision"


@pytest.mark.parametrize(("decision", "payout"), [("approve", 0), ("decline", 50)])
def test_payout_must_fit_the_decision(client, decision, payout):
    start(client, "CLM-1001")
    assert decide(client, "CLM-1001", decision, payout).status_code == 422


def test_pay_claim(client):
    approved(client, "CLM-1001", 420)
    claim = pay(client, "CLM-1001", 420).json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 420
    assert claim["payment"]["authorized_by"] == "agent"


def test_paying_again_is_done(client):
    """A step can run again after a restart: the same payment returns the claim,
    paid once, and another amount is refused."""
    approved(client, "CLM-1001", 420)
    pay(client, "CLM-1001", 420)
    again = pay(client, "CLM-1001", 420)
    assert again.status_code == 200
    assert again.json()["payment"]["amount"] == 420
    response = pay(client, "CLM-1001", 400)
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 is already paid"


def test_deciding_again_is_done(client):
    approved(client, "CLM-1001", 420)
    again = decide(client, "CLM-1001", "approve", 420)
    assert again.status_code == 200
    assert len(again.json()["decisions"]) == 1
    assert again.json()["status"] == "in_progress"
    assert decide(client, "CLM-1001", "approve", 400).status_code == 409


def test_pay_another_amount(client):
    approved(client, "CLM-1001", 420)
    response = pay(client, "CLM-1001", 500)
    assert response.status_code == 409
    assert response.json()["detail"] == "The approved payout is $420.00"
    assert client.get("/api/claims/CLM-1001").json()["payment"] is None


@pytest.mark.parametrize("decision", [None, "decline", "refer"])
def test_pay_a_claim_not_approved(client, decision):
    start(client, "CLM-1001")
    if decision:
        decide(client, "CLM-1001", decision, 0)
    response = pay(client, "CLM-1001", 420)
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 is not approved"


def test_payment_over_the_limit_waits_for_sign_off(client):
    approved(client, "CLM-1002", 1150)
    response = pay(client, "CLM-1002", 1150)
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "A payout over $1,000.00 waits for a handler's sign-off"
    )
    claim = client.get("/api/claims/CLM-1002").json()
    assert claim["status"] == "awaiting_sign_off"
    assert claim["payment"] is None


@pytest.mark.parametrize(
    ("payout", "status"),
    [(1000.00, "decided"), (1000.01, "awaiting_sign_off")],
)
def test_approval_limit(client, payout, status):
    approved(client, "CLM-1001", payout)
    pay(client, "CLM-1001", payout)
    assert client.get("/api/claims/CLM-1001").json()["status"] == status


def test_resolve_referral_with_approval(client):
    referred(client, "CLM-1010")
    claim = resolve(client, "CLM-1010", "HND-02", "approve", 1350).json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 1350
    assert claim["payment"]["authorized_by"] == "HND-02"
    agent, handler = claim["decisions"]
    assert agent["decided_by"] == "agent"
    assert agent["decision"] == "refer"
    assert agent["reasons"] == "The agent's reasons to refer."
    assert handler["decided_by"] == "HND-02"
    assert handler["decision"] == "approve"
    assert handler["reasons"] == "The handler's reasons."
    assert handler["policy_section"] is None


def test_resolve_referral_with_decline(client):
    referred(client, "CLM-1010")
    claim = resolve(client, "CLM-1010", "HND-03", "decline", 0).json()
    assert claim["status"] == "decided"
    assert claim["payment"] is None
    assert claim["decisions"][-1]["decision"] == "decline"


def test_resolve_needs_a_referred_claim(client):
    approved(client, "CLM-1002", 1150)
    response = resolve(client, "CLM-1002", "HND-02", "approve", 1150)
    assert response.status_code == 409


def test_resolve_by_unknown_handler(client):
    referred(client, "CLM-1010")
    assert resolve(client, "CLM-1010", "HND-99", "decline", 0).status_code == 404


def test_handler_cannot_refer(client):
    referred(client, "CLM-1010")
    assert resolve(client, "CLM-1010", "HND-02", "refer", 0).status_code == 422


def test_queue_shows_decisions_and_payments(client):
    approved(client, "CLM-1001", 420)
    pay(client, "CLM-1001", 420)
    approved(client, "CLM-1002", 1150)
    referred(client, "CLM-1010")
    resolve(client, "CLM-1010", "HND-02", "decline", 0)
    queue = {c["claim_id"]: c for c in client.get("/api/claims").json()}
    assert (queue["CLM-1001"]["decision"], queue["CLM-1001"]["paid"]) == (
        "approve",
        420,
    )
    assert (queue["CLM-1002"]["payout"], queue["CLM-1002"]["paid"]) == (1150, None)
    assert queue["CLM-1010"]["decision"] == "decline"
    assert queue["CLM-1003"]["decision"] is None


def test_a_run_stops_at_its_cap(client):
    run_id = client.post(
        "/api/runs", json={"mode": "queue", "cap": 2, "model": "ollama:qwen3.5:4b"}
    ).json()["run_id"]
    assert start(client, "CLM-1001", run_id).status_code == 200
    assert start(client, "CLM-1002", run_id).status_code == 200
    third = start(client, "CLM-1003", run_id)
    assert third.status_code == 409
    assert third.json()["detail"] == f"Run {run_id} has reached its cap of 2 claims"
    assert client.get("/api/claims/CLM-1003").json()["status"] == "waiting"


def test_a_claim_tried_again_counts_once_against_the_cap(client):
    run_id = client.post(
        "/api/runs", json={"mode": "queue", "cap": 1, "model": "ollama:qwen3.5:4b"}
    ).json()["run_id"]
    start(client, "CLM-1001", run_id)
    fail(client, "CLM-1001")
    assert start(client, "CLM-1001", run_id).status_code == 200


def test_a_claim_needs_a_running_run(client):
    run_id = a_run(client)
    client.post(f"/api/runs/{run_id}/finish", json={"summary": "Done."})
    response = start(client, "CLM-1001", run_id)
    assert response.status_code == 409
    assert response.json()["detail"] == f"Run {run_id} is finished, not running"


def test_a_failure_puts_the_claim_back_in_the_queue(client):
    start(client, "CLM-1001")
    claim = fail(client, "CLM-1001").json()
    assert claim["status"] == "waiting"
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert steps[-1]["kind"] == "failure"
    assert steps[-1]["text"] == "The model provider timed out"


def test_a_second_failure_leaves_the_claim_for_a_handler(client):
    start(client, "CLM-1001")
    fail(client, "CLM-1001")
    start(client, "CLM-1001")
    assert fail(client, "CLM-1001").json()["status"] == "left_for_handler"
    assert start(client, "CLM-1001").status_code == 409


def test_a_claim_with_a_decision_is_never_failed(client):
    approved(client, "CLM-1001", 420)
    response = fail(client, "CLM-1001")
    assert response.status_code == 409
    claim = client.get("/api/claims/CLM-1001").json()
    assert (claim["status"], len(claim["decisions"])) == ("in_progress", 1)


def test_a_claim_shows_its_latest_attempt(client):
    run_id = a_run(client)
    assert client.get("/api/claims/CLM-1001").json()["attempts"] == 0
    start(client, "CLM-1001", run_id)
    claim = client.get("/api/claims/CLM-1001").json()
    assert (claim["run_id"], claim["thread_id"], claim["attempts"]) == (
        run_id,
        "CLM-1001-test",
        1,
    )


def test_only_a_claim_in_progress_can_fail(client):
    assert fail(client, "CLM-1001").status_code == 409
    referred(client, "CLM-1010")
    assert fail(client, "CLM-1010").status_code == 409


def test_a_handler_decides_a_claim_left_for_them(client):
    start(client, "CLM-1004")
    fail(client, "CLM-1004")
    start(client, "CLM-1004")
    fail(client, "CLM-1004")
    claim = resolve(client, "CLM-1004", "HND-01", "approve", 74).json()
    assert claim["status"] == "decided"
    assert claim["payment"]["authorized_by"] == "HND-01"


def test_a_claim_moves_on_once_from_what_was_seen(client):
    """Two changes at once that both read the same revision: only one is made."""
    start(client, "CLM-1001")
    with db.engine().begin() as conn:
        seen = claims.revision(conn, "CLM-1001") or 0
        assert claims.move(conn, "CLM-1001", seen, "decided")
        assert not claims.move(conn, "CLM-1001", seen, "referred")
    assert client.get("/api/claims/CLM-1001").json()["status"] == "decided"
