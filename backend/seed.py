"""Load UnderCover's records from data/ into the database: `uv run -m
backend.seed` resets the database the settings name, Supabase when .env has
DATABASE_URL."""

import json
from functools import cache
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, Engine

from backend import db
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


def seed(conn: Connection) -> None:
    """Load every record, with each claim waiting in the queue."""
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


def fresh(conn: Connection) -> None:
    """Drop the backend's tables and seed them afresh, leaving any other tables,
    such as the agent's checkpoints, alone."""
    db.drop_tables(conn)
    db.create_tables(conn)
    seed(conn)


@cache
def ready(engine: Engine) -> None:
    """Seed the records the first time this process finds a database without
    them, or without any claims, as after a seed that failed partway."""
    with engine.begin() as conn:
        if not db.has_tables(conn) or claims.count(conn) == 0:
            fresh(conn)


def reset() -> None:
    """Reset the database the settings name to the records in data/."""
    with db.engine().begin() as conn:
        fresh(conn)


if __name__ == "__main__":
    reset()
    print(f"Reset {db.where(db.engine())}")
