"""The agent's runs, the claims each one works, and each claim's attempts."""

from typing import Any

from sqlalchemy import Connection, RowMapping, func, insert, select, update

from backend import db


def add(conn: Connection, run: dict[str, Any]) -> int:
    """Record a new run, running, given as kind, agents, model, reasoning_effort
    and started_at; return its id."""
    added = insert(db.runs).values(status="running", **run)
    return conn.execute(added.returning(db.runs.c.run_id)).scalar_one()


def run(conn: Connection, run_id: int) -> RowMapping | None:
    found = select(db.runs).where(db.runs.c.run_id == run_id)
    return conn.execute(found).mappings().first()


def latest(conn: Connection, kind: str) -> int | None:
    """The newest run of a kind, or None before the first."""
    found = select(func.max(db.runs.c.run_id)).where(db.runs.c.kind == kind)
    return conn.execute(found).scalar_one()


def set_claims(conn: Connection, run_id: int, claim_ids: list[str]) -> None:
    """Record the claims a run works, in order, in place of any before."""
    conn.execute(db.run_claims.delete().where(db.run_claims.c.run_id == run_id))
    if claim_ids:
        conn.execute(
            insert(db.run_claims),
            [
                {"run_id": run_id, "position": position, "claim_id": claim_id}
                for position, claim_id in enumerate(claim_ids)
            ],
        )


def claims_of(conn: Connection, run_id: int) -> list[str]:
    """A run's claims, in the order it takes them."""
    found = (
        select(db.run_claims.c.claim_id)
        .where(db.run_claims.c.run_id == run_id)
        .order_by(db.run_claims.c.position)
    )
    return list(conn.execute(found).scalars())


def finish(
    conn: Connection, run_id: int, status: str, summary: str | None, at: str
) -> None:
    conn.execute(
        update(db.runs)
        .where(db.runs.c.run_id == run_id)
        .values(status=status, summary=summary, finished_at=at)
    )


def stop_running(conn: Connection, at: str) -> list[int]:
    """Mark every run still running as stopped; return their ids."""
    stopped = conn.execute(
        update(db.runs)
        .where(db.runs.c.status == "running")
        .values(status="stopped", finished_at=at)
        .returning(db.runs.c.run_id)
    )
    return sorted(stopped.scalars())


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
