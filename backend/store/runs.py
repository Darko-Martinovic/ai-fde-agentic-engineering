"""The agent's runs, the claims each run started, and what its model calls used."""

from typing import Any

from sqlalchemy import Connection, RowMapping, func, insert, select, update

from backend import db


def add(conn: Connection, run: dict[str, Any]) -> int:
    """Record a new run, given as mode, cap, model and started_at; return its id."""
    added = insert(db.runs).values(status="running", todos="[]", **run)
    return conn.execute(added.returning(db.runs.c.run_id)).scalar_one()


def run(conn: Connection, run_id: int) -> RowMapping | None:
    found = select(db.runs).where(db.runs.c.run_id == run_id)
    return conn.execute(found).mappings().first()


def latest(conn: Connection) -> int | None:
    return conn.execute(select(func.max(db.runs.c.run_id))).scalar_one()


def set_todos(conn: Connection, run_id: int, todos: str) -> None:
    conn.execute(update(db.runs).where(db.runs.c.run_id == run_id).values(todos=todos))


def finish(
    conn: Connection, run_id: int, status: str, summary: str | None, at: str
) -> None:
    conn.execute(
        update(db.runs)
        .where(db.runs.c.run_id == run_id)
        .values(status=status, summary=summary, finished_at=at)
    )


def stop_running(conn: Connection, at: str) -> None:
    """Mark every run still running as stopped."""
    conn.execute(
        update(db.runs)
        .where(db.runs.c.status == "running")
        .values(status="stopped", finished_at=at)
    )


def add_attempt(
    conn: Connection, run_id: int | None, claim_id: str, thread_id: str, at: str
) -> None:
    conn.execute(
        insert(db.attempts).values(
            run_id=run_id, claim_id=claim_id, thread_id=thread_id, started_at=at
        )
    )


def attempts(conn: Connection, claim_id: str) -> list[RowMapping]:
    """A claim's attempts, each with its run and thread, the latest last."""
    attempt = db.attempts.c
    found = (
        select(attempt.run_id, attempt.thread_id)
        .where(attempt.claim_id == claim_id)
        .order_by(attempt.attempt_id)
    )
    return list(conn.execute(found).mappings())


def claims_started(conn: Connection, run_id: int) -> set[str]:
    found = select(db.attempts.c.claim_id).where(db.attempts.c.run_id == run_id)
    return set(conn.execute(found).scalars())


def add_usage(conn: Connection, run_id: int, usage: dict[str, Any]) -> None:
    """Record one model call, given as claim_id, model, input_tokens,
    output_tokens, cost, seconds and recorded_at."""
    conn.execute(insert(db.usage).values(run_id=run_id, **usage))


def usage(conn: Connection, run_id: int) -> RowMapping:
    used = db.usage.c
    found = select(
        func.count().label("model_calls"),
        func.coalesce(func.sum(used.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(used.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(used.cost), 0).label("cost"),
        func.coalesce(func.sum(used.seconds), 0).label("seconds"),
    ).where(used.run_id == run_id)
    return conn.execute(found).mappings().one()
