"""What the backend's routes share: the database for a request, the time, and
loading a claim."""

import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException

from backend import db
from backend.models import Claim
from backend.seed import ensure_seeded
from backend.store import claims


def database() -> Iterator[sqlite3.Connection]:
    """Open the database for one request, seeding it on first use."""
    conn = db.connect()
    ensure_seeded(conn)
    try:
        yield conn
    finally:
        conn.close()


Db = Annotated[sqlite3.Connection, Depends(database)]


def now() -> str:
    return datetime.now(UTC).isoformat()


def found[T](record: T | None, label: str, key: str) -> T:
    """Return the record, or raise a 404 when there's none."""
    if record is None:
        raise HTTPException(404, f"{label} {key} not found")
    return record


def load_claim(conn: sqlite3.Connection, claim_id: str) -> Claim:
    """Load one claim with its state, its decisions and its payment."""
    row = found(claims.claim(conn, claim_id), "Claim", claim_id)
    return Claim.model_validate(
        json.loads(row["data"])
        | {
            "status": row["status"],
            "decisions": claims.decisions(conn, claim_id),
            "payment": claims.payment(conn, claim_id),
        }
    )
