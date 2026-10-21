"""Load UnderCover's records from data/ into the database."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from backend import db
from backend.config import database_path
from backend.store import claims, records

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
    with conn:
        claims.insert(conn, read("claims.json"))
        records.insert(
            conn,
            policies=read("policies.json"),
            customers=read("customers.json"),
            handler_records=read("handlers.json"),
            settings={
                "plans": json.dumps(read("plans.json")),
                "company": json.dumps(read("company.json")),
                "policy_wording": read("policy_wording.md"),
                "claims_manual": read("claims_manual.md"),
            },
        )


def ensure_seeded(conn: sqlite3.Connection) -> None:
    """Seed the database if it has no claims yet."""
    if claims.count(conn) == 0:
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
