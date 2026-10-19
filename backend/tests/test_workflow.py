import pytest


def start(client, claim_id):
    return client.post(f"/api/claims/{claim_id}/start")


def decide(client, claim_id, decision, payout):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": decision,
            "payout": payout,
            "reasons": f"The agent's reasons to {decision}.",
            "policy_section": "Section 3, Trip Delay",
        },
    )


def pay(client, claim_id, amount):
    return client.post(f"/api/claims/{claim_id}/payment", json={"amount": amount})


def sign_off(client, claim_id, handler_id):
    return client.post(
        f"/api/claims/{claim_id}/sign-off", json={"handler_id": handler_id}
    )


def resolve(client, claim_id, handler_id, decision, payout):
    return client.post(
        f"/api/claims/{claim_id}/resolution",
        json={
            "handler_id": handler_id,
            "decision": decision,
            "payout": payout,
            "reasons": "The handler's reasons.",
        },
    )


def approved(client, claim_id, payout):
    start(client, claim_id)
    return decide(client, claim_id, "approve", payout)


def referred(client, claim_id):
    start(client, claim_id)
    return decide(client, claim_id, "refer", 0)


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


def test_pay_twice(client):
    approved(client, "CLM-1001", 420)
    pay(client, "CLM-1001", 420)
    response = pay(client, "CLM-1001", 420)
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 is already paid"


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

    claim = sign_off(client, "CLM-1002", "HND-01").json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 1150
    assert claim["payment"]["authorized_by"] == "HND-01"
    assert pay(client, "CLM-1002", 1150).status_code == 409


@pytest.mark.parametrize(
    ("payout", "status"),
    [(1000.00, "decided"), (1000.01, "awaiting_sign_off")],
)
def test_approval_limit(client, payout, status):
    approved(client, "CLM-1001", payout)
    pay(client, "CLM-1001", payout)
    assert client.get("/api/claims/CLM-1001").json()["status"] == status


def test_sign_off_needs_a_claim_awaiting_sign_off(client):
    approved(client, "CLM-1001", 420)
    response = sign_off(client, "CLM-1001", "HND-01")
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Claim CLM-1001 is in_progress, not awaiting_sign_off"
    )


def test_sign_off_by_unknown_handler(client):
    approved(client, "CLM-1002", 1150)
    response = sign_off(client, "CLM-1002", "HND-99")
    assert response.status_code == 404
    assert response.json()["detail"] == "Handler HND-99 not found"


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
