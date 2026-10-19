"""What the backend's routes share: the database for a request and loading records."""

import json
import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException

from backend import db
from backend.models import Claim
from backend.seed import ensure_seeded


def database() -> Iterator[sqlite3.Connection]:
    """Open the database for one request, seeding it on first use."""
    conn = db.connect()
    ensure_seeded(conn)
    try:
        yield conn
    finally:
        conn.close()


Db = Annotated[sqlite3.Connection, Depends(database)]


def find(conn: sqlite3.Connection, sql: str, key: str, label: str) -> sqlite3.Row:
    """Return the one row the query finds for the key, or raise a 404."""
    row = conn.execute(sql, (key,)).fetchone()
    if row is None:
        raise HTTPException(404, f"{label} {key} not found")
    return row


def setting(conn: sqlite3.Connection, name: str) -> str:
    """Return one stored setting."""
    return conn.execute(
        "SELECT value FROM settings WHERE name = ?", (name,)
    ).fetchone()[0]


def load_claim(conn: sqlite3.Connection, claim_id: str) -> Claim:
    """Load one claim with its state, its decisions and its payment."""
    row = find(
        conn,
        "SELECT data, status FROM claims WHERE claim_id = ?",
        claim_id,
        "Claim",
    )
    decisions = conn.execute(
        "SELECT decided_by, decision, payout, reasons, policy_section, decided_at"
        " FROM decisions WHERE claim_id = ? ORDER BY decision_id",
        (claim_id,),
    ).fetchall()
    payment = conn.execute(
        "SELECT amount, authorized_by, paid_at FROM payments WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()
    return Claim.model_validate(
        json.loads(row["data"])
        | {
            "status": row["status"],
            "decisions": [dict(d) for d in decisions],
            "payment": dict(payment) if payment else None,
        }
    )
