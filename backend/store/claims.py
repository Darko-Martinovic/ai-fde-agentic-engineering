"""The claims, their decisions and their payments."""

import json
import sqlite3
from typing import Any

QUEUE = """
WITH latest AS (
    SELECT claim_id, decision, payout FROM decisions
    WHERE decision_id IN (SELECT MAX(decision_id) FROM decisions GROUP BY claim_id)
)
SELECT claims.data, claims.status, customers.data AS customer,
    latest.decision, latest.payout, payments.amount AS paid
FROM claims
JOIN customers USING (customer_id)
LEFT JOIN latest USING (claim_id)
LEFT JOIN payments USING (claim_id)
ORDER BY claim_id
"""


def queue(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every claim with its customer, its latest decision and its payment."""
    return conn.execute(QUEUE).fetchall()


def claim(conn: sqlite3.Connection, claim_id: str) -> sqlite3.Row | None:
    """A claim's record and state, or None if there's no such claim."""
    return conn.execute(
        "SELECT data, status FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone()


def every_claim(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT claim_id, status, data FROM claims").fetchall()


def count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]


def count_in(conn: sqlite3.Connection, status: str) -> int:
    """How many claims are in one state."""
    return conn.execute(
        "SELECT COUNT(*) FROM claims WHERE status = ?", (status,)
    ).fetchone()[0]


def first_in_progress(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT claim_id FROM claims WHERE status = 'in_progress' ORDER BY claim_id"
    ).fetchone()
    return row["claim_id"] if row else None


def set_status(conn: sqlite3.Connection, claim_id: str, status: str) -> None:
    conn.execute("UPDATE claims SET status = ? WHERE claim_id = ?", (status, claim_id))


def return_to_queue(conn: sqlite3.Connection) -> None:
    """Put claims in progress back to waiting, clearing their unpaid decisions."""
    conn.execute(
        "DELETE FROM decisions WHERE claim_id IN"
        " (SELECT claim_id FROM claims WHERE status = 'in_progress')"
    )
    conn.execute("UPDATE claims SET status = 'waiting' WHERE status = 'in_progress'")


def decisions(conn: sqlite3.Connection, claim_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT decided_by, decision, payout, reasons, policy_section, decided_at"
        " FROM decisions WHERE claim_id = ? ORDER BY decision_id",
        (claim_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def agent_decisions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT claim_id, decision, payout, policy_section FROM decisions"
        " WHERE decided_by = 'agent'"
    ).fetchall()


def add_decision(
    conn: sqlite3.Connection, claim_id: str, decision: dict[str, Any]
) -> None:
    """Record a decision, given as decided_by, decision, payout, reasons,
    policy_section and decided_at."""
    conn.execute(
        "INSERT INTO decisions (claim_id, decided_by, decision, payout, reasons,"
        " policy_section, decided_at) VALUES (:claim_id, :decided_by, :decision,"
        " :payout, :reasons, :policy_section, :decided_at)",
        {"claim_id": claim_id} | decision,
    )


def payment(conn: sqlite3.Connection, claim_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT amount, authorized_by, paid_at FROM payments WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()
    return dict(row) if row else None


def payments(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT claim_id, amount, authorized_by FROM payments"
    ).fetchall()


def add_payment(
    conn: sqlite3.Connection, claim_id: str, amount: float, by: str, at: str
) -> None:
    conn.execute("INSERT INTO payments VALUES (?, ?, ?, ?)", (claim_id, amount, by, at))


def insert(conn: sqlite3.Connection, claims: list[dict[str, Any]]) -> None:
    """Store the claims seeded from data/, each waiting in the queue."""
    conn.executemany(
        "INSERT INTO claims VALUES (?, ?, ?, 'waiting', ?)",
        [
            (c["claim_id"], c["policy_id"], c["customer_id"], json.dumps(c))
            for c in claims
        ],
    )
