"""The records the claims refer to: policies, customers, handlers, and the
stored settings (the plans, the company's rules and the documents)."""

import json
import sqlite3
from typing import Any


def policy(conn: sqlite3.Connection, policy_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT data FROM policies WHERE policy_id = ?", (policy_id,)
    ).fetchone()
    return json.loads(row["data"]) if row else None


def customer(conn: sqlite3.Connection, customer_id: str) -> str | None:
    """Return a customer's record as JSON, or None if there's no such customer."""
    row = conn.execute(
        "SELECT data FROM customers WHERE customer_id = ?", (customer_id,)
    ).fetchone()
    return row["data"] if row else None


def handlers(conn: sqlite3.Connection) -> list[str]:
    """Return every handler's record as JSON, in id order."""
    rows = conn.execute("SELECT data FROM handlers ORDER BY handler_id").fetchall()
    return [row["data"] for row in rows]


def handler(conn: sqlite3.Connection, handler_id: str) -> str | None:
    """Return a handler's record as JSON, or None if there's no such handler."""
    row = conn.execute(
        "SELECT data FROM handlers WHERE handler_id = ?", (handler_id,)
    ).fetchone()
    return row["data"] if row else None


def stored(conn: sqlite3.Connection, name: str) -> str:
    """Return one stored setting, such as the plans or the policy wording."""
    return conn.execute(
        "SELECT value FROM settings WHERE name = ?", (name,)
    ).fetchone()[0]


def insert(
    conn: sqlite3.Connection,
    policies: list[dict[str, Any]],
    customers: list[dict[str, Any]],
    handler_records: list[dict[str, Any]],
    settings: dict[str, str],
) -> None:
    """Store the records seeded from data/."""
    conn.executemany(
        "INSERT INTO policies VALUES (?, ?)",
        [(p["policy_id"], json.dumps(p)) for p in policies],
    )
    conn.executemany(
        "INSERT INTO customers VALUES (?, ?)",
        [(c["customer_id"], json.dumps(c)) for c in customers],
    )
    conn.executemany(
        "INSERT INTO handlers VALUES (?, ?)",
        [(h["handler_id"], json.dumps(h)) for h in handler_records],
    )
    conn.executemany("INSERT INTO settings VALUES (?, ?)", list(settings.items()))
