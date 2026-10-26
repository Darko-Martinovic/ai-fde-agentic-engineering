import logging

import httpx

from backend import agent_service
from backend.agent_service import resume_claim as real_resume_claim  # not the stand-in
from backend.tests.workflow_steps import approved, decide, fail, pay, review

NOTE = "The suit is limited to $300.00 under the per-item limit."


def test_a_sign_off_hands_the_claim_back_to_the_agent(client, resumed):
    approved(client, "CLM-1003", 3750)
    claim = review(client, "CLM-1003", "HND-01").json()
    assert (claim["status"], claim["payment"]) == ("in_progress", None)
    signed = claim["decisions"][-1]
    assert (signed["review"], signed["reviewed_by"]) == ("signed_off", "HND-01")
    assert signed["reviewed_at"]
    assert resumed == ["CLM-1003"]

    paid = pay(client, "CLM-1003", 3750).json()
    assert paid["status"] == "decided"
    assert paid["payment"]["authorized_by"] == "HND-01"
    assert paid["payment"]["signed_off_at"] == signed["reviewed_at"]


def test_the_agent_is_told_once_the_review_is_saved(client, monkeypatch):
    seen = []

    def look(claim_id):
        seen.append(client.get(f"/api/claims/{claim_id}").json()["decisions"][-1])

    monkeypatch.setattr(agent_service, "resume_claim", look)
    approved(client, "CLM-1003", 3750)
    review(client, "CLM-1003", "HND-01")
    [decision] = seen
    assert decision["review"] == "signed_off"


def test_a_review_stands_when_the_agent_cant_be_reached(monkeypatch, caplog):
    def unreachable(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", unreachable)
    with caplog.at_level(logging.WARNING, logger=agent_service.__name__):
        real_resume_claim("CLM-1003")
    assert "didn't pick up CLM-1003" in caplog.text


def test_a_held_payout_isnt_paid_before_a_sign_off(client):
    approved(client, "CLM-1003", 3750)
    response = pay(client, "CLM-1003", 3750)
    assert response.status_code == 409
    assert client.get("/api/claims/CLM-1003").json()["payment"] is None


def test_a_review_needs_a_known_handler(client, resumed):
    approved(client, "CLM-1003", 3750)
    response = review(client, "CLM-1003", "HND-99")
    assert (response.status_code, response.json()["detail"]) == (
        404,
        "Handler HND-99 not found",
    )
    assert resumed == []


def test_a_review_needs_a_held_payout(client, resumed):
    approved(client, "CLM-1001", 420)
    response = review(client, "CLM-1001", "HND-01")
    assert (response.status_code, response.json()["detail"]) == (
        409,
        "Claim CLM-1001 is in_progress, not awaiting_sign_off",
    )
    assert resumed == []


def test_a_rejection_hands_the_note_back_to_the_agent(client, resumed):
    approved(client, "CLM-1002", 1350)
    claim = review(client, "CLM-1002", "HND-02", approved=False, note=NOTE).json()
    assert claim["status"] == "in_progress"
    rejected = claim["decisions"][-1]
    assert (rejected["review"], rejected["reviewed_by"]) == ("rejected", "HND-02")
    assert rejected["review_note"] == NOTE
    assert resumed == ["CLM-1002"]


def test_a_rejection_needs_a_note(client):
    approved(client, "CLM-1002", 1350)
    response = review(client, "CLM-1002", "HND-02", approved=False, note="  ")
    assert response.status_code == 422


def test_after_a_rejection_the_agents_decision_goes_back_to_a_handler(client):
    approved(client, "CLM-1002", 1350)
    review(client, "CLM-1002", "HND-02", approved=False, note=NOTE)
    again = decide(client, "CLM-1002", "approve", 500).json()
    assert again["status"] == "awaiting_sign_off"
    assert len(again["decisions"]) == 2
    response = pay(client, "CLM-1002", 500)
    assert response.status_code == 409
    assert "after a rejection" in response.json()["detail"]


def test_a_decline_after_a_rejection_is_referred(client):
    approved(client, "CLM-1002", 1350)
    review(client, "CLM-1002", "HND-02", approved=False, note=NOTE)
    assert decide(client, "CLM-1002", "decline", 0).json()["status"] == "referred"


def test_a_second_rejection_refers_the_claim(client, resumed):
    approved(client, "CLM-1002", 1350)
    review(client, "CLM-1002", "HND-02", approved=False, note=NOTE)
    decide(client, "CLM-1002", "approve", 1300)
    claim = review(client, "CLM-1002", "HND-01", approved=False, note=NOTE).json()
    assert claim["status"] == "referred"
    assert resumed == ["CLM-1002"]


def test_a_failure_after_a_rejection_is_left_for_a_handler(client):
    approved(client, "CLM-1002", 1350)
    review(client, "CLM-1002", "HND-02", approved=False, note=NOTE)
    claim = fail(client, "CLM-1002").json()
    assert claim["status"] == "left_for_handler"
    assert len(claim["decisions"]) == 1
