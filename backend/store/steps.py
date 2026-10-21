"""The steps the agent takes on each claim."""

import sqlite3


def add(conn: sqlite3.Connection, claim_id: str, step: dict[str, str]) -> None:
    """Record a step, given as thread_id, kind, text and recorded_at."""
    conn.execute(
        "INSERT INTO steps (claim_id, thread_id, kind, text, recorded_at)"
        " VALUES (:claim_id, :thread_id, :kind, :text, :recorded_at)",
        {"claim_id": claim_id} | step,
    )


def of_claim(conn: sqlite3.Connection, claim_id: str) -> list[sqlite3.Row]:
    """A claim's steps, in the order they were recorded."""
    return conn.execute(
        "SELECT thread_id, kind, text, recorded_at FROM steps WHERE claim_id = ?"
        " ORDER BY step_id",
        (claim_id,),
    ).fetchall()


def every_step(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every claim's steps, in the order they were recorded."""
    return conn.execute(
        "SELECT claim_id, thread_id, kind, text, recorded_at FROM steps"
        " ORDER BY step_id"
    ).fetchall()
