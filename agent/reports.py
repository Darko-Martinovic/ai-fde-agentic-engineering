"""The line each piece of work on a claim reports, from the backend's record of
the claim."""

from typing import Any

# Where a claim stands, as the backend records it, for the states the agent
# works from
IN_PROGRESS, WAITING, DECIDED = "in_progress", "waiting", "decided"
AWAITING_SIGN_OFF = "awaiting_sign_off"
# How a claim's report reads, by the claim's state and by the agent's decision
BY_STATE = {
    DECIDED: "paid",
    IN_PROGRESS: "not paid yet",
    AWAITING_SIGN_OFF: "waiting for a handler's sign-off",
    WAITING: "failed, back in the queue",
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
