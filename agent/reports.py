"""The line each piece of work on a claim reports, from the backend's record of
the claim."""

from typing import Any

# How a claim's report reads, by the claim's state and by the agent's decision
BY_STATE = {
    "decided": "paid",
    "in_progress": "not paid yet",
    "awaiting_sign_off": "waiting for a handler's sign-off",
    "waiting": "failed, back in the queue",
    "left_for_handler": "failed twice, left for a handler",
}
BY_DECISION = {"decline": "declined", "refer": "referred to a handler"}


def report(claim: dict[str, Any]) -> str:
    """The line a claim's work reports: its outcome, from the backend's record,
    with the reasons for a decline or a referral, which the handlers need."""
    claim_id, status = claim["claim_id"], claim["status"]
    decision = claim["decisions"][-1] if claim["decisions"] else None
    if decision is None or status == "left_for_handler":
        return f"{claim_id}: {BY_STATE[status]}"
    if decision["decision"] != "approve":
        outcome = BY_DECISION[decision["decision"]]
        return f"{claim_id}: {outcome}, because: {decision['reasons']}"
    return f"{claim_id}: approved ${decision['payout']:,.2f}, {BY_STATE[status]}"
