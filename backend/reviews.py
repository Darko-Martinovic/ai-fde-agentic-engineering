"""What the claims handlers do on a claim: review a held payout, signing it off
or rejecting it with a note, which hands the claim back to the agent, and decide
a claim the agent referred or that was left for them."""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend import agent_service
from backend.api import Db, found, load_claim, now
from backend.claim_rules import (
    MAX_REJECTIONS,
    add_decision,
    add_payment,
    check_handler,
    refuse_copy,
    rejections,
    require_status,
)
from backend.models import FOR_A_HANDLER, Claim, HandlerDecisionIn, ReviewIn
from backend.store import claims

router = APIRouter(prefix="/api/claims/{claim_id}")


@router.post("/review", operation_id="review_payout")
def review_payout(
    claim_id: str, review: ReviewIn, conn: Db, background: BackgroundTasks
) -> Claim:
    """Sign off a held payout as a handler, or reject it with a note, for the agent."""
    seen = found(claims.revision(conn, claim_id), "Claim", claim_id)
    claim = load_claim(conn, claim_id)
    refuse_copy(claim)
    check_handler(conn, review.handler_id)
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
            "reviewed_by": review.handler_id,
            "reviewed_at": now(),
            "review_note": review.note.strip() or None,
        },
    )
    if not referred:
        # Runs once the review is committed and the response sent
        background.add_task(agent_service.resume_claim, claim_id)
    return load_claim(conn, claim_id)


@router.post("/handler-decision", operation_id="decide_as_handler")
def decide_as_handler(claim_id: str, resolution: HandlerDecisionIn, conn: Db) -> Claim:
    """Approve or decline, as a handler, a claim the agent referred or that was
    left for a handler, paying an approval."""
    claim = load_claim(conn, claim_id)
    refuse_copy(claim)
    check_handler(conn, resolution.handler_id)
    require_status(claim, *FOR_A_HANDLER)
    add_decision(conn, claim_id, resolution.handler_id, resolution, None)
    if resolution.decision == "approve":
        add_payment(conn, claim_id, resolution.payout, resolution.handler_id, None)
    claims.set_status(conn, claim_id, "decided")
    return load_claim(conn, claim_id)
