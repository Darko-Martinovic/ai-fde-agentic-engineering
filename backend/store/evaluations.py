"""The answer key and evaluations' copies: the held-out claims, the handlers'
decisions on both labelled sets, and the copies of a set's claims that an
evaluation works. The only module that reads the handlers' decisions."""

import json
from typing import Any

from sqlalchemy import Connection, RowMapping, func, insert, select

from backend import db

# Who the agent's decisions are recorded as
AGENT = "agent"


def add_held_out(conn: Connection, claims: list[dict[str, Any]]) -> None:
    """Store the held-out claims, out of the queue."""
    conn.execute(
        insert(db.held_out_claims),
        [{"claim_id": c["claim_id"], "data": json.dumps(c)} for c in claims],
    )


def add_handler_decisions(
    conn: Connection, evaluation_set: str, decisions: list[dict[str, Any]]
) -> None:
    """Store the handlers' decisions on one labelled set."""
    conn.execute(
        insert(db.handler_decisions),
        [
            {
                "evaluation_set": evaluation_set,
                "claim_id": d["claim_id"],
                "decision": d["decision"],
                "payout": d["payout"],
                "tiny": d["tiny"],
                "reason": d["reason"],
                "reference": d["reference"],
            }
            for d in decisions
        ],
    )


def handler_decisions(conn: Connection, evaluation_set: str) -> dict[str, RowMapping]:
    """The handlers' decisions on a set, by the claim they decided."""
    decision = db.handler_decisions.c
    found = select(
        decision.claim_id, decision.decision, decision.payout, decision.tiny
    ).where(decision.evaluation_set == evaluation_set)
    return {row["claim_id"]: row for row in conn.execute(found).mappings()}


def handlers_reasons(
    conn: Connection, evaluation_set: str
) -> dict[str, dict[str, Any]]:
    """The handlers' decisions on a set with their reasons and references, by
    the claim they decided, for the judge."""
    decision = db.handler_decisions.c
    found = select(
        decision.claim_id, decision.decision, decision.reason, decision.reference
    ).where(decision.evaluation_set == evaluation_set)
    return {
        row["claim_id"]: {
            "decision": row["decision"],
            "reason": row["reason"],
            "reference": row["reference"],
        }
        for row in conn.execute(found).mappings()
    }


def originals(conn: Connection, evaluation_set: str) -> list[dict[str, Any]]:
    """A set's claim records: the queue's own claims for the evaluation set,
    the held-out claims for the held-out set, oldest submitted first."""
    table = db.claims if evaluation_set == "evaluation" else db.held_out_claims
    found = select(table.c.data)
    if table is db.claims:
        found = found.where(db.claims.c.evaluation_id.is_(None))
    records = [json.loads(data) for data in conn.execute(found).scalars()]
    return sorted(records, key=lambda c: (c["submitted_on"], c["claim_id"]))


def agents_answers(conn: Connection, run_id: int) -> dict[str, RowMapping]:
    """Each copy in an evaluation, by its id: the claim it copies, and the
    agent's latest decision on it, its payout, its reasons and the section they
    rest on, or none."""
    decision = db.decisions.c
    latest = (
        select(
            decision.claim_id,
            decision.decision,
            decision.payout,
            decision.reasons,
            decision.policy_section,
        )
        .where(
            decision.decision_id.in_(
                select(func.max(decision.decision_id))
                .where(decision.decided_by == AGENT)
                .group_by(decision.claim_id)
            )
        )
        .subquery()
    )
    found = (
        select(
            db.claims.c.claim_id,
            db.claims.c.copy_of,
            latest.c.decision,
            latest.c.payout,
            latest.c.reasons,
            latest.c.policy_section,
        )
        .outerjoin(latest, latest.c.claim_id == db.claims.c.claim_id)
        .where(db.claims.c.evaluation_id == run_id)
    )
    return {row["claim_id"]: row for row in conn.execute(found).mappings()}


def add_copies(conn: Connection, run_id: int, copies: list[dict[str, Any]]) -> None:
    """Store an evaluation's copies of claims, each waiting, given as the copy's
    record and the id of the claim it copies."""
    conn.execute(
        insert(db.claims),
        [
            {
                "claim_id": c["record"]["claim_id"],
                "policy_id": c["record"]["policy_id"],
                "customer_id": c["record"]["customer_id"],
                "status": "waiting",
                "data": json.dumps(c["record"]),
                "evaluation_id": run_id,
                "copy_of": c["copy_of"],
            }
            for c in copies
        ],
    )
