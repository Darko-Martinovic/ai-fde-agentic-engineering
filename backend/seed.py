"""Load UnderCover's records from data/ into the database."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from backend import db
from backend.config import database_path

DATA_DIR = Path(__file__).parent.parent / "data"

# The only files the backend reads. data/evals/ and data/security/ stay out of reach.
SEED_FILES = (
    "claims.json",
    "policies.json",
    "customers.json",
    "plans.json",
    "handlers.json",
    "company.json",
    "policy_wording.md",
    "claims_manual.md",
)


def read(name: str) -> Any:
    """Read one seed file, parsing JSON files."""
    text = (DATA_DIR / name).read_text(encoding="utf-8")
    return json.loads(text) if name.endswith(".json") else text


def seed(conn: sqlite3.Connection) -> None:
    """Load every record, with each claim waiting in the queue."""
    claims = read("claims.json")
    with conn:
        conn.executemany(
            "INSERT INTO claims VALUES (?, ?, ?, 'waiting', ?)",
            [
                (c["claim_id"], c["policy_id"], c["customer_id"], json.dumps(c))
                for c in claims
            ],
        )
        conn.executemany(
            "INSERT INTO policies VALUES (?, ?)",
            [(p["policy_id"], json.dumps(p)) for p in read("policies.json")],
        )
        conn.executemany(
            "INSERT INTO customers VALUES (?, ?)",
            [(c["customer_id"], json.dumps(c)) for c in read("customers.json")],
        )
        conn.executemany(
            "INSERT INTO handlers VALUES (?, ?)",
            [(h["handler_id"], json.dumps(h)) for h in read("handlers.json")],
        )
        conn.executemany(
            "INSERT INTO settings VALUES (?, ?)",
            [
                ("plans", json.dumps(read("plans.json"))),
                ("company", json.dumps(read("company.json"))),
                ("policy_wording", read("policy_wording.md")),
                ("claims_manual", read("claims_manual.md")),
            ],
        )


def ensure_seeded(conn: sqlite3.Connection) -> None:
    """Seed the database if it has no claims yet."""
    if conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0:
        seed(conn)


def reset() -> None:
    """Delete the database and seed a fresh one."""
    database_path().unlink(missing_ok=True)
    conn = db.connect()
    seed(conn)
    conn.close()


if __name__ == "__main__":
    reset()
    print(f"Reset {database_path()}")
