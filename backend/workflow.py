"""How the agent moves a claim through the queue: starting it, its steps, its
decision and its payment, and a failure."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import Connection

from backend.api import Db, found, load_claim, now
from backend.callers import AGENT, HANDLER
from backend.claim_rules import (
    add_decision,
    add_payment,
    approval_limit,
    held,
    require_status,
    status_after,
)
from backend.models import (
    Claim,
    DecisionIn,
    FailureIn,
    PaymentIn,
    StartIn,
    Step,
    StepIn,
)
from backend.round_views import cut_short
from backend.run_views import require_running
from backend.store import claims, runs, steps

router = APIRouter(prefix="/api/claims/{claim_id}")

# A claim that fails this many times is left for a handler
MAX_FAILURES = 2
# The agent can never pay more than the approval limit: only a sign-off does
OVER_THE_LIMIT = "A payment over ${limit:,.2f} needs a handler's sign-off"


@router.post("/start", operation_id="start_claim", dependencies=[AGENT])
def start_claim(claim_id: str, start: StartIn, conn: Db) -> Claim:
    """Start work on a waiting claim, in a running run or on its own."""
    claim = load_claim(conn, claim_id)
    require_status(claim, "waiting")
    if start.run_id is not None:
        require_running(conn, start.run_id)
    refuse_cut_short(conn, claim)
    if not claims.start(conn, claim_id):
        raise HTTPException(409, f"Claim {claim_id} has just been started")
    runs.add_attempt(conn, start.run_id, claim_id, start.thread_id, now())
    return load_claim(conn, claim_id)


def refuse_cut_short(conn: Connection, claim: Claim) -> None:
    """Refuse a copy in a round's evaluation once the round has ended or spent
    its limit."""
    if claim.evaluation_id is None:
        return
    run = found(runs.run(conn, claim.evaluation_id), "Run", str(claim.evaluation_id))
    round_id = run["round_id"]
    why = cut_short(conn, round_id) if round_id is not None else None
    if why:
        raise HTTPException(409, why)


@router.post("/failure", operation_id="fail_claim", dependencies=[AGENT])
def fail_claim(claim_id: str, failure: FailureIn, conn: Db) -> Claim:
    """Record that work on a claim failed before it was decided: the claim goes
    back in the queue, or is left for a handler when it has failed twice. A claim
    with a decision is never failed: the agent carries it on. One a handler
    rejected the payout on is left for a handler, with its decisions."""
    claim = load_claim(conn, claim_id)
    require_status(claim, "in_progress")
    latest = claim.decisions[-1] if claim.decisions else None
    if latest and latest.review != "rejected":
        raise HTTPException(409, f"Claim {claim_id} has a decision")
    failures = steps.count_of(conn, claim_id, "failure") + 1
    status = "left_for_handler" if failures >= MAX_FAILURES or latest else "waiting"
    step = {"thread_id": failure.thread_id, "kind": "failure", "text": failure.reason}
    steps.add(conn, claim_id, step | {"recorded_at": now()})
    claims.set_status(conn, claim_id, status)
    return load_claim(conn, claim_id)


@router.post("/steps", operation_id="record_step", dependencies=[AGENT])
def record_step(claim_id: str, step: StepIn, conn: Db) -> Step:
    """Record one step the agent took on a claim."""
    load_claim(conn, claim_id)
    row = step.model_dump() | {"recorded_at": now()}
    steps.add(conn, claim_id, row)
    return Step.model_validate(row)


@router.get("/steps", operation_id="list_steps", dependencies=[HANDLER])
def list_steps(claim_id: str, conn: Db) -> list[Step]:
    """List the steps the agent took on a claim, in order."""
    load_claim(conn, claim_id)
    return [Step.model_validate(dict(row)) for row in steps.of_claim(conn, claim_id)]


def repeated_decision(claim: Claim, decision: DecisionIn) -> Claim:
    """The agent's decision the claim already has, as when the agent carries on
    after a restart, is done: return the claim. Any other decision is refused,
    unless a handler rejected the payout, when the agent decides again."""
    recorded = claim.decisions[-1]
    if (recorded.decided_by, recorded.decision, recorded.payout) != (
        "agent",
        decision.decision,
        round(decision.payout, 2),
    ):
        raise HTTPException(409, f"Claim {claim.claim_id} already has a decision")
    return claim


@router.post("/decision", operation_id="record_decision", dependencies=[AGENT])
def record_decision(claim_id: str, decision: DecisionIn, conn: Db) -> Claim:
    """Approve, decline or refer a claim in progress, with the payout and reasons."""
    seen = found(claims.revision(conn, claim_id), "Claim", claim_id)
    claim = load_claim(conn, claim_id)
    if claim.decisions and claim.decisions[-1].review != "rejected":
        return repeated_decision(claim, decision)
    require_status(claim, "in_progress")
    limit = approval_limit(conn)
    status = status_after(claim, decision, limit)
    if not claims.move(conn, claim_id, seen, status):
        # Another request decided the claim first, as when the agent asks twice
        # at once: this one is a repeat of it, or refused
        return repeated_decision(load_claim(conn, claim_id), decision)
    add_decision(conn, claim_id, "agent", decision, limit)
    return load_claim(conn, claim_id)


@router.post("/payment", operation_id="pay_claim", dependencies=[AGENT])
def pay_claim(claim_id: str, payment: PaymentIn, conn: Db) -> Claim:
    """Pay an approved claim its payout, up to the approval limit, once only."""
    refuse_over_the_limit(conn, payment.amount)
    seen = found(claims.revision(conn, claim_id), "Claim", claim_id)
    claim = load_claim(conn, claim_id)
    approval = claim.decisions[-1] if claim.decisions else None
    if claim.payment:
        return repeated_payment(claim, payment)
    if approval is None or approval.decision != "approve":
        raise HTTPException(409, f"Claim {claim_id} is not approved")
    reason = held(claim, approval)
    if reason:
        raise HTTPException(409, reason)
    if round(payment.amount, 2) != approval.payout:
        raise HTTPException(409, f"The approved payout is ${approval.payout:,.2f}")
    if not claims.move(conn, claim_id, seen, "decided"):
        return repeated_payment(load_claim(conn, claim_id), payment)
    # A sign-off pays the claim itself, so only the agent pays here
    add_payment(conn, claim_id, approval.payout, "agent", None)
    return load_claim(conn, claim_id)


def refuse_over_the_limit(conn: Connection, amount: float) -> None:
    """Refuse a payment over the approval limit, whatever the claim, with a 403
    that names the limit: only a handler's sign-off pays one."""
    limit = approval_limit(conn)
    if round(amount, 2) > limit:
        raise HTTPException(403, OVER_THE_LIMIT.format(limit=limit))


def repeated_payment(claim: Claim, payment: PaymentIn) -> Claim:
    """A payment the claim already has, as after a restart, is done: return the
    claim. Another amount, or a payment on a claim that has moved on, is refused."""
    if claim.payment is None or claim.payment.amount != round(payment.amount, 2):
        raise HTTPException(409, f"Claim {claim.claim_id} is already paid")
    return claim
