"""The claims, their decisions and their payments."""

import json
from typing import Any

from sqlalchemy import ColumnElement, Connection, RowMapping, func, select, update
from sqlalchemy import insert as insert_into

from backend import db


def queue(conn: Connection, evaluation_id: int | None) -> list[RowMapping]:
    """Every claim of the queue (`evaluation_id` None), or every copy in an
    evaluation, with its customer, its latest decision and its payment."""
    decision = db.decisions.c
    latest = (
        select(decision.claim_id, decision.decision, decision.payout)
        .where(
            decision.decision_id.in_(
                select(func.max(decision.decision_id)).group_by(decision.claim_id)
            )
        )
        .subquery()
    )
    found = (
        select(
            db.claims.c.data,
            db.claims.c.status,
            db.customers.c.data.label("customer"),
            latest.c.decision,
            latest.c.payout,
            db.payments.c.amount.label("paid"),
        )
        .join(db.customers, db.customers.c.customer_id == db.claims.c.customer_id)
        .outerjoin(latest, latest.c.claim_id == db.claims.c.claim_id)
        .outerjoin(db.payments, db.payments.c.claim_id == db.claims.c.claim_id)
        .where(in_evaluation(evaluation_id))
        .order_by(db.claims.c.claim_id)
    )
    return list(conn.execute(found).mappings())


def in_evaluation(evaluation_id: int | None) -> ColumnElement[bool]:
    """The claims of the queue, for None, or the copies in an evaluation."""
    column = db.claims.c.evaluation_id
    return column.is_(None) if evaluation_id is None else column == evaluation_id


def claim(conn: Connection, claim_id: str) -> RowMapping | None:
    """A claim's record and state, and the evaluation a copy is in and the
    claim it copies, or None if there's no such claim."""
    claim = db.claims.c
    found = select(claim.data, claim.status, claim.evaluation_id, claim.copy_of).where(
        claim.claim_id == claim_id
    )
    return conn.execute(found).mappings().first()


def every_claim(conn: Connection) -> list[RowMapping]:
    """Every claim of the queue, leaving out evaluations' copies."""
    found = select(db.claims.c.claim_id, db.claims.c.status, db.claims.c.data).where(
        in_evaluation(None)
    )
    return list(conn.execute(found).mappings())


def count(conn: Connection) -> int:
    return conn.execute(select(func.count()).select_from(db.claims)).scalar_one()


def count_in(conn: Connection, status: str) -> int:
    """How many claims are in one state."""
    found = select(func.count()).where(db.claims.c.status == status)
    return conn.execute(found).scalar_one()


def first_in_progress(conn: Connection) -> str | None:
    found = (
        select(db.claims.c.claim_id)
        .where(db.claims.c.status == "in_progress")
        .order_by(db.claims.c.claim_id)
    )
    return conn.execute(found).scalars().first()


def start(conn: Connection, claim_id: str) -> bool:
    """Move a waiting claim to in progress, in one step so two starts can't both
    take it. Return whether this start took it."""
    taken = conn.execute(
        update(db.claims)
        .where(db.claims.c.claim_id == claim_id, db.claims.c.status == "waiting")
        .values(status="in_progress")
    )
    return taken.rowcount == 1


def revision(conn: Connection, claim_id: str) -> int | None:
    """How many times the claim's decision or payment has changed, or None if
    there's no such claim. Read it before the claim, to move the claim on."""
    found = select(db.claims.c.revision).where(db.claims.c.claim_id == claim_id)
    return conn.execute(found).scalar_one_or_none()


def move(conn: Connection, claim_id: str, seen: int, status: str) -> bool:
    """Move a claim to a new state if nothing has changed its decision or payment
    since revision `seen`, in one step so two changes at once can't both be
    made. Return whether this one was."""
    moved = conn.execute(
        update(db.claims)
        .where(db.claims.c.claim_id == claim_id, db.claims.c.revision == seen)
        .values(status=status, revision=db.claims.c.revision + 1)
    )
    return moved.rowcount == 1


def set_status(conn: Connection, claim_id: str, status: str) -> None:
    conn.execute(
        update(db.claims).where(db.claims.c.claim_id == claim_id).values(status=status)
    )


def decisions(conn: Connection, claim_id: str) -> list[dict[str, Any]]:
    decision = db.decisions.c
    found = (
        select(
            decision.decided_by,
            decision.decision,
            decision.payout,
            decision.reasons,
            decision.policy_section,
            decision.decided_at,
            decision.review,
            decision.reviewed_by,
            decision.reviewed_at,
            decision.review_note,
            decision.approval_limit,
        )
        .where(decision.claim_id == claim_id)
        .order_by(decision.decision_id)
    )
    return [dict(row) for row in conn.execute(found).mappings()]


def agent_decisions(conn: Connection) -> list[RowMapping]:
    decision = db.decisions.c
    found = (
        select(
            decision.claim_id,
            decision.decision,
            decision.payout,
            decision.policy_section,
        )
        .where(decision.decided_by == "agent")
        .order_by(decision.decision_id)
    )
    return list(conn.execute(found).mappings())


def review(conn: Connection, claim_id: str, reviewed: dict[str, Any]) -> None:
    """Record a handler's review on the claim's latest decision, given as review,
    reviewed_by, reviewed_at and review_note."""
    decision = db.decisions.c
    latest = select(func.max(decision.decision_id)).where(decision.claim_id == claim_id)
    conn.execute(
        update(db.decisions)
        .where(decision.decision_id == latest.scalar_subquery())
        .values(**reviewed)
    )


def add_decision(conn: Connection, claim_id: str, decision: dict[str, Any]) -> None:
    """Record a decision, given as decided_by, decision, payout, reasons,
    policy_section and decided_at."""
    conn.execute(insert_into(db.decisions).values(claim_id=claim_id, **decision))


def payment(conn: Connection, claim_id: str) -> dict[str, Any] | None:
    paid = db.payments.c
    found = select(
        paid.amount, paid.authorized_by, paid.paid_at, paid.signed_off_at
    ).where(paid.claim_id == claim_id)
    row = conn.execute(found).mappings().first()
    return dict(row) if row else None


def payments(conn: Connection) -> list[RowMapping]:
    paid = db.payments.c
    found = select(paid.claim_id, paid.amount, paid.authorized_by)
    return list(conn.execute(found).mappings())


def add_payment(conn: Connection, claim_id: str, paid: dict[str, Any]) -> None:
    """Record a payment, given as amount, authorized_by, paid_at and
    signed_off_at."""
    conn.execute(insert_into(db.payments).values(claim_id=claim_id, **paid))


def insert(conn: Connection, claims: list[dict[str, Any]]) -> None:
    """Store the claims seeded from data/, each waiting in the queue."""
    conn.execute(
        insert_into(db.claims),
        [
            {
                "claim_id": c["claim_id"],
                "policy_id": c["policy_id"],
                "customer_id": c["customer_id"],
                "status": "waiting",
                "data": json.dumps(c),
            }
            for c in claims
        ],
    )
