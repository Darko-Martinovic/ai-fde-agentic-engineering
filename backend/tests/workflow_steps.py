"""The workflow's steps through the API, for the backend's tests."""

from backend.tests.claim_starts import start


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


def review(client, claim_id, handler_id, approved=True, note=""):
    """A handler's review of a held payout: a sign-off, or a rejection."""
    return client.post(
        f"/api/claims/{claim_id}/review",
        json={"handler_id": handler_id, "approved": approved, "note": note},
    )


def resolve(client, claim_id, handler_id, decision, payout):
    return client.post(
        f"/api/claims/{claim_id}/handler-decision",
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


def fail(client, claim_id, reason="The model provider timed out"):
    return client.post(
        f"/api/claims/{claim_id}/failure",
        json={"thread_id": f"{claim_id}-test", "reason": reason},
    )
