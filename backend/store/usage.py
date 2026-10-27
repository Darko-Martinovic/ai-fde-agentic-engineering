"""What the claim agents' work costs: each model call's tokens and cost, and each
spell of work on a claim, with the run it happened in, or none."""

from typing import Any

from sqlalchemy import Connection, RowMapping, func, insert, select

from backend import db


def add_model_call(conn: Connection, claim_id: str, call: dict[str, Any]) -> None:
    """Record one model call, given as thread_id, run_id, model, input_tokens,
    output_tokens, cost, seconds and recorded_at."""
    conn.execute(insert(db.model_calls).values(claim_id=claim_id, **call))


def add_work_time(conn: Connection, claim_id: str, spell: dict[str, Any]) -> None:
    """Record one spell of work, given as thread_id, run_id, started_at and
    seconds."""
    conn.execute(insert(db.work_times).values(claim_id=claim_id, **spell))


def run_model_calls(conn: Connection, run_id: int) -> RowMapping:
    """A run's model calls added up: how many, their tokens, cost and seconds."""
    call = db.model_calls.c
    found = select(
        func.count().label("model_calls"),
        func.coalesce(func.sum(call.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(call.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(call.cost), 0).label("cost"),
        func.coalesce(func.sum(call.seconds), 0).label("seconds"),
    ).where(call.run_id == run_id)
    return conn.execute(found).mappings().one()
