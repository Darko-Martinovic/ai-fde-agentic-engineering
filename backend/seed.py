"""Load UnderCover's records from data/ into the database: `uv run -m
backend.seed` resets the database the settings name, Supabase when .env has
DATABASE_URL."""

import json
from functools import cache
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, Engine

from backend import db
from backend.store import claims, evaluations, records

DATA_DIR = Path(__file__).parent.parent / "data"

# The files the backend serves its records from. data/security/ stays out of
# reach, and of data/evals/ only the answer key below is read, by seeding alone.
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
# The answer key, which only seeding reads, into tables no claim operation reads:
# the held-out claims, and the handlers' decisions on each labelled set
ANSWER_KEY = DATA_DIR / "evals"
HELD_OUT_CLAIMS = "held_out_claims.json"
HANDLER_DECISIONS = {
    "evaluation": "decisions.json",
    "held_out": "held_out_decisions.json",
}


def read(name: str, folder: Path = DATA_DIR) -> Any:
    """Read one seed file, parsing JSON files."""
    text = (folder / name).read_text(encoding="utf-8")
    return json.loads(text) if name.endswith(".json") else text


def seed_answer_key(conn: Connection) -> str:
    """Load the held-out claims and the handlers' decisions, for evaluations,
    and say how many."""
    held_out = read(HELD_OUT_CLAIMS, ANSWER_KEY)
    evaluations.add_held_out(conn, held_out)
    decided = 0
    for evaluation_set, name in HANDLER_DECISIONS.items():
        decisions = read(name, ANSWER_KEY)
        evaluations.add_handler_decisions(conn, evaluation_set, decisions)
        decided += len(decisions)
    return f"{len(held_out)} held-out claims and {decided} handlers' decisions"


def seed(conn: Connection) -> str:
    """Load every record, with each claim waiting in the queue, and say what
    the answer key holds."""
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
    return seed_answer_key(conn)


def fresh(conn: Connection) -> str:
    """Drop the backend's tables and seed them afresh, leaving any other tables,
    such as the agent's checkpoints, alone."""
    db.drop_tables(conn)
    db.create_tables(conn)
    return seed(conn)


@cache
def ready(engine: Engine) -> None:
    """Seed the records the first time this process finds a database without
    them, or without any claims, as after a seed that failed partway."""
    with engine.begin() as conn:
        if not db.has_tables(conn) or claims.count(conn) == 0:
            fresh(conn)


def reset() -> str:
    """Reset the database the settings name to the records in data/, and say
    what the answer key holds."""
    with db.engine().begin() as conn:
        return fresh(conn)


if __name__ == "__main__":
    answer_key = reset()
    print(f"Reset {db.where(db.engine())}, with {answer_key} for evaluations")
