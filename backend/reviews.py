"""What the claims handlers do on a claim, signed in: review a held payout,
signing it off or rejecting it with a note, which hands the claim back to the
agent, and decide a claim the agent referred or that was left for them. Only a
handler who can sign off payouts over the limit reviews a held payout or
approves one over the limit."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend import agent_service
from backend.api import Db, found, load_claim, now
from backend.claim_rules import (
    MAX_REJECTIONS,
    add_decision,
    add_payment,
    approval_limit,
    refuse_copy,
    rejections,
    require_status,
)
from backend.models import FOR_A_HANDLER, Claim, Handler, HandlerDecisionIn, ReviewIn
from backend.signed_in import SignedIn, refuse_unless_senior, senior
from backend.store import claims

router = APIRouter(prefix="/api/claims/{claim_id}")

Reviewer = Annotated[Handler, senior("review this payout")]


@router.post("/review", operation_id="review_payout")
def review_payout(
    claim_id: str,
    review: ReviewIn,
    handler: Reviewer,
    conn: Db,
    background: BackgroundTasks,
) -> Claim:
    """Sign off a held payout as the signed-in handler, or reject it with a note."""
    seen = found(claims.revision(conn, claim_id), "Claim", claim_id)
    claim = load_claim(conn, claim_id)
    refuse_copy(claim)
    require_status(claim, "awaiting_sign_off")
    referred = not review.approved and rejections(claim) + 1 >= MAX_REJECTIONS
    status = "referred" if referred else "in_progress"
    if not claims.move(conn, claim_id, seen, status):
        raise HTTPException(409, f"Claim {claim_id} has just been reviewed")
    claims.review(
        conn,
        claim_id,
        {
            "review": "signed_off" if review.approved else "rejected",
            "reviewed_by": handler.handler_id,
            "reviewed_at": now(),
            "review_note": review.note.strip() or None,
        },
    )
    if not referred:
        # Runs once the review is committed and the response sent
        background.add_task(agent_service.resume_claim, claim_id)
    return load_claim(conn, claim_id)


@router.post("/handler-decision", operation_id="decide_as_handler")
def decide_as_handler(
    claim_id: str, resolution: HandlerDecisionIn, handler: SignedIn, conn: Db
) -> Claim:
    """Approve or decline, as the signed-in handler, a claim the agent referred or
    that was left for a handler, paying an approval."""
    claim = load_claim(conn, claim_id)
    refuse_copy(claim)
    require_status(claim, *FOR_A_HANDLER)
    limit = approval_limit(conn)
    if resolution.decision == "approve" and resolution.payout > limit:
        refuse_unless_senior(handler, "approve this payout", limit)
    add_decision(conn, claim_id, handler.handler_id, resolution, None)
    if resolution.decision == "approve":
        add_payment(conn, claim_id, resolution.payout, handler.handler_id, None)
    claims.set_status(conn, claim_id, "decided")
    return load_claim(conn, claim_id)
