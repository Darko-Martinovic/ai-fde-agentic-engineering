"""How a claim moves through the queue, and the rule that holds large payments."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import Connection

from backend.api import Db, company, found, load_claim, now, require_running
from backend.models import (
    FOR_A_HANDLER,
    Claim,
    DecisionIn,
    FailureIn,
    HandlerDecisionIn,
    PaymentIn,
    SignOffIn,
    StartIn,
    Step,
    StepIn,
)
from backend.store import claims, records, runs, steps

router = APIRouter(prefix="/api/claims/{claim_id}")

STATUS_AFTER = {"decline": "decided", "refer": "referred"}
# A claim that fails this many times is left for a handler
MAX_FAILURES = 2


def approval_limit(conn: Connection) -> float:
    """Return the payout above which a handler must sign off."""
    return company(conn)["payout_approval_limit"]


def check_handler(conn: Connection, handler_id: str) -> None:
    found(records.handler(conn, handler_id), "Handler", handler_id)


def require_status(claim: Claim, *statuses: str) -> None:
    if claim.status not in statuses:
        wanted = " or ".join(statuses)
        raise HTTPException(
            409, f"Claim {claim.claim_id} is {claim.status}, not {wanted}"
        )


def add_decision(
    conn: Connection,
    claim_id: str,
    decided_by: str,
    decision: DecisionIn | HandlerDecisionIn,
    policy_section: str | None,
) -> None:
    claims.add_decision(
        conn,
        claim_id,
        {
            "decided_by": decided_by,
            "decision": decision.decision,
            "payout": round(decision.payout, 2),
            "reasons": decision.reasons,
            "policy_section": policy_section,
            "decided_at": now(),
        },
    )


def add_payment(
    conn: Connection, claim_id: str, amount: float, authorized_by: str
) -> None:
    claims.add_payment(conn, claim_id, round(amount, 2), authorized_by, now())


@router.post("/start", operation_id="start_claim")
def start_claim(claim_id: str, start: StartIn, conn: Db) -> Claim:
    """Start work on a waiting claim in a run, within the run's cap."""
    require_status(load_claim(conn, claim_id), "waiting")
    run = require_running(conn, start.run_id)
    started = run.claims_started
    if claim_id not in started and len(started) >= run.cap:
        raise HTTPException(
            409, f"Run {run.run_id} has reached its cap of {run.cap} claims"
        )
    if not claims.start(conn, claim_id):
        raise HTTPException(409, f"Claim {claim_id} has just been started")
    runs.add_attempt(conn, run.run_id, claim_id, start.thread_id, now())
    return load_claim(conn, claim_id)


@router.post("/failure", operation_id="fail_claim")
def fail_claim(claim_id: str, failure: FailureIn, conn: Db) -> Claim:
    """Record that work on a claim failed before it was decided: the claim goes
    back in the queue, or is left for a handler when it has failed twice."""
    require_status(load_claim(conn, claim_id), "in_progress")
    failures = steps.count_of(conn, claim_id, "failure") + 1
    status = "left_for_handler" if failures >= MAX_FAILURES else "waiting"
    step = {"thread_id": failure.thread_id, "kind": "failure", "text": failure.reason}
    claims.clear_decisions(conn, claim_id)
    steps.add(conn, claim_id, step | {"recorded_at": now()})
    claims.set_status(conn, claim_id, status)
    return load_claim(conn, claim_id)


@router.post("/steps", operation_id="record_step")
def record_step(claim_id: str, step: StepIn, conn: Db) -> Step:
    """Record one step the agent took on a claim."""
    load_claim(conn, claim_id)
    row = step.model_dump() | {"recorded_at": now()}
    steps.add(conn, claim_id, row)
    return Step.model_validate(row)


@router.get("/steps", operation_id="list_steps")
def list_steps(claim_id: str, conn: Db) -> list[Step]:
    """List the steps the agent took on a claim, in order."""
    load_claim(conn, claim_id)
    return [Step.model_validate(dict(row)) for row in steps.of_claim(conn, claim_id)]


@router.post("/decision", operation_id="decide_claim")
def decide_claim(claim_id: str, decision: DecisionIn, conn: Db) -> Claim:
    """Approve, decline or refer a claim in progress, with the payout and reasons."""
    claim = load_claim(conn, claim_id)
    require_status(claim, "in_progress")
    if claim.decisions:
        raise HTTPException(409, f"Claim {claim_id} already has a decision")
    if decision.decision == "approve":
        over_limit = decision.payout > approval_limit(conn)
        status = "awaiting_sign_off" if over_limit else "in_progress"
    else:
        status = STATUS_AFTER[decision.decision]
    add_decision(conn, claim_id, "agent", decision, decision.policy_section)
    claims.set_status(conn, claim_id, status)
    return load_claim(conn, claim_id)


@router.post("/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: PaymentIn, conn: Db) -> Claim:
    """Pay an approved claim its payout, if no handler's sign-off is needed."""
    claim = load_claim(conn, claim_id)
    approval = claim.decisions[-1] if claim.decisions else None
    limit = approval_limit(conn)
    if claim.payment:
        raise HTTPException(409, f"Claim {claim_id} is already paid")
    if approval is None or approval.decision != "approve":
        raise HTTPException(409, f"Claim {claim_id} is not approved")
    if approval.payout > limit:
        raise HTTPException(
            409, f"A payout over ${limit:,.2f} waits for a handler's sign-off"
        )
    if round(payment.amount, 2) != approval.payout:
        raise HTTPException(409, f"The approved payout is ${approval.payout:,.2f}")
    add_payment(conn, claim_id, approval.payout, "agent")
    claims.set_status(conn, claim_id, "decided")
    return load_claim(conn, claim_id)


@router.post("/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, sign_off: SignOffIn, conn: Db) -> Claim:
    """Sign off a large approved payout as a handler, which pays it."""
    claim = load_claim(conn, claim_id)
    check_handler(conn, sign_off.handler_id)
    require_status(claim, "awaiting_sign_off")
    add_payment(conn, claim_id, claim.decisions[-1].payout, sign_off.handler_id)
    claims.set_status(conn, claim_id, "decided")
    return load_claim(conn, claim_id)


@router.post("/handler-decision", operation_id="decide_as_handler")
def decide_as_handler(claim_id: str, resolution: HandlerDecisionIn, conn: Db) -> Claim:
    """Approve or decline, as a handler, a claim the agent referred or that was
    left for a handler, paying an approval."""
    claim = load_claim(conn, claim_id)
    check_handler(conn, resolution.handler_id)
    require_status(claim, *FOR_A_HANDLER)
    add_decision(conn, claim_id, resolution.handler_id, resolution, None)
    if resolution.decision == "approve":
        add_payment(conn, claim_id, resolution.payout, resolution.handler_id)
    claims.set_status(conn, claim_id, "decided")
    return load_claim(conn, claim_id)
