"""The rules a claim's decisions and payments follow, whoever makes them: the
agent's routes in workflow.py and the handlers' in reviews.py."""

from fastapi import HTTPException
from sqlalchemy import Connection

from backend.api import now
from backend.models import Claim, ClaimStatus, Decision, DecisionIn, HandlerDecisionIn
from backend.store import claims, platform_settings

STATUS_AFTER: dict[str, ClaimStatus] = {"decline": "decided", "refer": "referred"}
# A held payout rejected this many times is referred to a handler
MAX_REJECTIONS = 2


def approval_limit(conn: Connection) -> float:
    """The payout above which a handler must sign off, as the settings stand."""
    return platform_settings.current(conn)["approval_limit"]


def refuse_copy(claim: Claim) -> None:
    """Nobody reviews or decides an evaluation's copy: it's scored on the
    agent's work alone."""
    if claim.evaluation_id is not None:
        raise HTTPException(
            409,
            f"Claim {claim.claim_id} is a copy in an evaluation and can't be"
            " reviewed or decided",
        )


def require_status(claim: Claim, *statuses: str) -> None:
    if claim.status not in statuses:
        wanted = " or ".join(statuses)
        raise HTTPException(
            409, f"Claim {claim.claim_id} is {claim.status}, not {wanted}"
        )


def rejections(claim: Claim) -> int:
    """How many times a handler has rejected the agent's payout on the claim."""
    return sum(decision.review == "rejected" for decision in claim.decisions)


def status_after(claim: Claim, decision: DecisionIn, limit: float) -> ClaimStatus:
    """Where the agent's decision puts the claim. After a handler has rejected a
    payout, the agent's next decision always goes back to a handler: an approval
    waits for a sign-off whatever its size, and anything else is referred."""
    if rejections(claim):
        return "awaiting_sign_off" if decision.decision == "approve" else "referred"
    if decision.decision != "approve":
        return STATUS_AFTER[decision.decision]
    over_limit = decision.payout > limit
    return "awaiting_sign_off" if over_limit else "in_progress"


def held(claim: Claim, approval: Decision) -> str | None:
    """Why an approval can't be paid without a handler's sign-off, or None when it
    can: it's over the limit, or follows a rejection, and isn't signed off."""
    if approval.review == "signed_off":
        return None
    limit = approval.approval_limit
    if approval.payout > limit:
        return f"A payout over ${limit:,.2f} waits for a handler's sign-off"
    if rejections(claim):
        return "A payout after a rejection waits for a handler's sign-off"
    return None


def add_decision(
    conn: Connection,
    claim_id: str,
    decided_by: str,
    decision: DecisionIn | HandlerDecisionIn,
    limit: float,
) -> None:
    """Record a decision with the approval limit it's held to: the agent's
    with the section it rests on, a handler's with none."""
    section = decision.policy_section if isinstance(decision, DecisionIn) else None
    claims.add_decision(
        conn,
        claim_id,
        {
            "decided_by": decided_by,
            "decision": decision.decision,
            "payout": round(decision.payout, 2),
            "reasons": decision.reasons,
            "policy_section": section,
            "decided_at": now(),
            "approval_limit": limit,
        },
    )


def add_payment(
    conn: Connection,
    claim_id: str,
    amount: float,
    authorized_by: str,
    signed_off_at: str | None,
) -> None:
    """Record a payment, with the handler who signed it off and when, if one did."""
    claims.add_payment(
        conn,
        claim_id,
        {
            "amount": round(amount, 2),
            "authorized_by": authorized_by,
            "paid_at": now(),
            "signed_off_at": signed_off_at,
        },
    )
