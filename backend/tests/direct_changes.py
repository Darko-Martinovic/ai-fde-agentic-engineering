"""Changing the records behind the API's back, for tests that need a state the
workflow takes too long to reach. Each change goes through the store, in a
transaction of its own, on the database the backend uses."""

import json
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection

from backend import db
from backend.seed import ready
from backend.store import claims, records, steps


@contextmanager
def records_in_use() -> Iterator[Connection]:
    """The database the backend uses, seeded, in one transaction."""
    ready(db.engine())
    with db.engine().begin() as conn:
        yield conn


def set_status(status, *claim_ids):
    """Put these claims, or every claim if none is named, in a state."""
    with records_in_use() as conn:
        named = claim_ids or [row["claim_id"] for row in claims.every_claim(conn)]
        for claim_id in named:
            claims.set_status(conn, claim_id, status)


def set_approval_limit(amount):
    """Change the payout approval limit stored with the company's rules."""
    with records_in_use() as conn:
        rules = json.loads(records.stored(conn, "company"))
        rules["payout_approval_limit"] = amount
        records.store(conn, "company", json.dumps(rules))


def add_steps(claim_id, thread_id, timed_steps):
    """Record steps at set times, given as (second, kind, text)."""
    with records_in_use() as conn:
        for second, kind, text in timed_steps:
            steps.add(
                conn,
                claim_id,
                {
                    "thread_id": thread_id,
                    "kind": kind,
                    "text": text,
                    "recorded_at": f"2026-10-19T10:00:{second:02d}+00:00",
                },
            )


def count_claims():
    with records_in_use() as conn:
        return claims.count(conn)
