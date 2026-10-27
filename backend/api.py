"""What the backend's routes share: the database for a request, the time, a
claim's line in the queue, and loading a claim."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, HTTPException
from sqlalchemy import Connection, RowMapping

from backend import db
from backend.models import Claim, ClaimSummary, Policy
from backend.seed import ready
from backend.store import claims, records, runs


def database() -> Iterator[Connection]:
    """The database for one request, in one transaction, seeded on first use. A
    request's work is committed when it succeeds and undone when it fails."""
    engine = db.engine()
    ready(engine)
    with engine.begin() as conn:
        yield conn


# Scoped to the route, so a request's work is committed before its response is
# sent and before any background task runs
Db = Annotated[Connection, Depends(database, scope="function")]


def now() -> str:
    return datetime.now(UTC).isoformat()


def found[T](record: T | None, label: str, key: str) -> T:
    """Return the record, or raise a 404 when there's none."""
    if record is None:
        raise HTTPException(404, f"{label} {key} not found")
    return record


def queue_line(row: RowMapping) -> ClaimSummary:
    """A claim's line in the queue, from its row in `claims.queue`."""
    return ClaimSummary.model_validate(
        json.loads(row["data"])
        | {
            "status": row["status"],
            "customer_name": json.loads(row["customer"])["name"],
            "decision": row["decision"],
            "payout": row["payout"],
            "paid": row["paid"],
        }
    )


def load_claim(conn: Connection, claim_id: str) -> Claim:
    """Load one claim with its state, its decisions and its payment."""
    row = found(claims.claim(conn, claim_id), "Claim", claim_id)
    attempts = runs.attempts(conn, claim_id)
    latest = attempts[-1] if attempts else {"run_id": None, "thread_id": None}
    return Claim.model_validate(
        json.loads(row["data"])
        | {
            "status": row["status"],
            "decisions": claims.decisions(conn, claim_id),
            "payment": claims.payment(conn, claim_id),
            "run_id": latest["run_id"],
            "thread_id": latest["thread_id"],
            "attempts": len(attempts),
            "evaluation_id": row["evaluation_id"],
            "copy_of": row["copy_of"],
        }
    )


def load_policy(conn: Connection, policy_id: str) -> Policy:
    """Load one policy with its plan's limits, its add-ons and the benefits the
    deductible applies to."""
    policy: dict[str, Any] = found(records.policy(conn, policy_id), "Policy", policy_id)
    plans = json.loads(records.stored(conn, "plans"))
    plan = next(p for p in plans["plans"] if p["plan"] == policy["plan"])
    add_ons = [a for a in plans["add_ons"] if a["add_on"] in policy["add_ons"]]
    return Policy.model_validate(
        policy
        | {
            "plan": plan,
            "add_ons": add_ons,
            "deductible_applies_to": plans["deductible_applies_to"],
        }
    )


def company(conn: Connection) -> dict[str, Any]:
    """The company's rules, such as the payout approval limit."""
    return json.loads(records.stored(conn, "company"))
