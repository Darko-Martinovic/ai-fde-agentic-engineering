"""Load UnderCover's records from data/ into the database: `uv run -m
backend.seed` resets the database the settings name, Supabase when .env has
DATABASE_URL."""

import json
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, Engine

from backend import db
from backend.free_model import free_model
from backend.store import claims, evaluations, platform_settings, records, versions
from backend.version_models import CLAIMS_TEAM, NO_EFFORT, Verdict

DATA_DIR = Path(__file__).parent.parent / "data"
INSTRUCTIONS = Path(__file__).parent / "instructions"
# The models the claim agent may use, and the one version 1 runs on
MODELS = "models.json"
# What a round of improvement works to, which with the approval limit in
# company.json make the first settings
IMPROVEMENT = "improvement.json"

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
    MODELS,
    IMPROVEMENT,
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


def models_allowed() -> list[dict[str, Any]]:
    """The models the claim agent may use: those in data/models.json, on their
    provider, or the free model in MODEL_NAME alone."""
    free = free_model()
    if free:
        return [free]
    listed = read(MODELS)
    return [model | {"provider": listed["provider"]} for model in listed["models"]]


def first_model() -> dict[str, str]:
    """The model version 1 runs on: the one data/models.json names for it, or
    the free model at no reasoning effort of its own."""
    free = free_model()
    if free:
        return {"model": free["model"], "reasoning_effort": NO_EFFORT}
    return read(MODELS)["first_version"]


def seed_configuration(conn: Connection, now: str) -> None:
    """Store the first settings, the models allowed and version 1 of the claim
    agent's configuration, kept: today's instructions on its first model."""
    limit = read("company.json")["payout_approval_limit"]
    first = {"approval_limit": limit} | read(IMPROVEMENT)
    platform_settings.add(conn, first, None, now)
    platform_settings.add_models(conn, models_allowed())
    versions.add(
        conn,
        first_model()
        | {
            "instructions": (INSTRUCTIONS / "claim.md").read_text(encoding="utf-8"),
            "based_on": None,
            "reason": "The claim agent as it was before versions.",
            "proposed_by": CLAIMS_TEAM,
            "created_at": now,
            "verdict": Verdict.KEPT,
            "verdict_reason": "The first version.",
            "decided_at": now,
        },
    )


def seed(conn: Connection) -> str:
    """Load every record, with each claim waiting in the queue, and version 1
    of the claim agent's configuration, and say what the answer key holds."""
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
    seed_configuration(conn, datetime.now(UTC).isoformat())
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
    print(
        f"Reset {db.where(db.engine())}, with {answer_key} for evaluations,"
        " and version 1 of the configuration"
    )
