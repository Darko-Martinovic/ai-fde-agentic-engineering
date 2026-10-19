"""How a claim moves through the queue, and the rule that holds large payments."""

import json
import sqlite3
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from backend.api import Db, find, load_claim, setting
from backend.models import (
    Claim,
    DecisionIn,
    PaymentIn,
    ResolutionIn,
    SignOffIn,
    Step,
    StepIn,
)

router = APIRouter(prefix="/api/claims/{claim_id}")

STATUS_AFTER = {"decline": "decided", "refer": "referred"}


def now() -> str:
    return datetime.now(UTC).isoformat()


def approval_limit(conn: sqlite3.Connection) -> float:
    """Return the payout above which a handler must sign off."""
    return json.loads(setting(conn, "company"))["payout_approval_limit"]


def check_handler(conn: sqlite3.Connection, handler_id: str) -> None:
    find(conn, "SELECT 1 FROM handlers WHERE handler_id = ?", handler_id, "Handler")


def require_status(claim: Claim, status: str) -> None:
    if claim.status != status:
        raise HTTPException(
            409, f"Claim {claim.claim_id} is {claim.status}, not {status}"
        )


def set_status(conn: sqlite3.Connection, claim_id: str, status: str) -> None:
    conn.execute("UPDATE claims SET status = ? WHERE claim_id = ?", (status, claim_id))


def add_decision(
    conn: sqlite3.Connection,
    claim_id: str,
    decided_by: str,
    decision: DecisionIn | ResolutionIn,
    policy_section: str | None,
) -> None:
    conn.execute(
        "INSERT INTO decisions (claim_id, decided_by, decision, payout, reasons,"
        " policy_section, decided_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            claim_id,
            decided_by,
            decision.decision,
            round(decision.payout, 2),
            decision.reasons,
            policy_section,
            now(),
        ),
    )


def add_payment(
    conn: sqlite3.Connection, claim_id: str, amount: float, authorized_by: str
) -> None:
    conn.execute(
        "INSERT INTO payments VALUES (?, ?, ?, ?)",
        (claim_id, round(amount, 2), authorized_by, now()),
    )


@router.post("/start", operation_id="start_claim")
def start_claim(claim_id: str, conn: Db) -> Claim:
    """Start work on a waiting claim."""
    require_status(load_claim(conn, claim_id), "waiting")
    with conn:
        set_status(conn, claim_id, "in_progress")
    return load_claim(conn, claim_id)


@router.post("/steps", operation_id="record_step")
def record_step(claim_id: str, step: StepIn, conn: Db) -> Step:
    """Record one step the agent took on a claim."""
    load_claim(conn, claim_id)
    recorded = Step(**step.model_dump(), recorded_at=datetime.now(UTC))
    with conn:
        conn.execute(
            "INSERT INTO steps (claim_id, thread_id, kind, text, recorded_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                claim_id,
                step.thread_id,
                step.kind,
                step.text,
                recorded.recorded_at.isoformat(),
            ),
        )
    return recorded


@router.get("/steps", operation_id="list_steps")
def list_steps(claim_id: str, conn: Db) -> list[Step]:
    """List the steps the agent took on a claim, in order."""
    load_claim(conn, claim_id)
    rows = conn.execute(
        "SELECT thread_id, kind, text, recorded_at FROM steps WHERE claim_id = ?"
        " ORDER BY step_id",
        (claim_id,),
    ).fetchall()
    return [Step.model_validate(dict(row)) for row in rows]


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
    with conn:
        add_decision(conn, claim_id, "agent", decision, decision.policy_section)
        set_status(conn, claim_id, status)
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
    with conn:
        add_payment(conn, claim_id, approval.payout, "agent")
        set_status(conn, claim_id, "decided")
    return load_claim(conn, claim_id)


@router.post("/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, sign_off: SignOffIn, conn: Db) -> Claim:
    """Sign off a large approved payout as a handler, which pays it."""
    claim = load_claim(conn, claim_id)
    check_handler(conn, sign_off.handler_id)
    require_status(claim, "awaiting_sign_off")
    with conn:
        add_payment(conn, claim_id, claim.decisions[-1].payout, sign_off.handler_id)
        set_status(conn, claim_id, "decided")
    return load_claim(conn, claim_id)


@router.post("/resolution", operation_id="resolve_referral")
def resolve_referral(claim_id: str, resolution: ResolutionIn, conn: Db) -> Claim:
    """Approve or decline a referred claim as a handler, paying an approval."""
    claim = load_claim(conn, claim_id)
    check_handler(conn, resolution.handler_id)
    require_status(claim, "referred")
    with conn:
        add_decision(conn, claim_id, resolution.handler_id, resolution, None)
        if resolution.decision == "approve":
            add_payment(conn, claim_id, resolution.payout, resolution.handler_id)
        set_status(conn, claim_id, "decided")
    return load_claim(conn, claim_id)
