"""The agent's runs, the claims each run started, and what its model calls used."""

import sqlite3
from typing import Any, cast

USAGE = """
SELECT COUNT(*) AS model_calls,
    COALESCE(SUM(input_tokens), 0) AS input_tokens,
    COALESCE(SUM(output_tokens), 0) AS output_tokens,
    COALESCE(SUM(cost), 0) AS cost,
    COALESCE(SUM(seconds), 0) AS seconds
FROM usage WHERE run_id = ?
"""


def add(conn: sqlite3.Connection, run: dict[str, Any]) -> int:
    """Record a new run, given as mode, cap, model and started_at; return its id."""
    cursor = conn.execute(
        "INSERT INTO runs (mode, cap, model, status, started_at, todos)"
        " VALUES (:mode, :cap, :model, 'running', :started_at, '[]')",
        run,
    )
    return cast(int, cursor.lastrowid)


def run(conn: sqlite3.Connection, run_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()


def latest(conn: sqlite3.Connection) -> int | None:
    return conn.execute("SELECT MAX(run_id) FROM runs").fetchone()[0]


def set_todos(conn: sqlite3.Connection, run_id: int, todos: str) -> None:
    conn.execute("UPDATE runs SET todos = ? WHERE run_id = ?", (todos, run_id))


def finish(
    conn: sqlite3.Connection, run_id: int, status: str, summary: str | None, at: str
) -> None:
    conn.execute(
        "UPDATE runs SET status = ?, summary = ?, finished_at = ? WHERE run_id = ?",
        (status, summary, at, run_id),
    )


def stop_running(conn: sqlite3.Connection, at: str) -> None:
    """Mark every run still running as stopped."""
    conn.execute(
        "UPDATE runs SET status = 'stopped', finished_at = ? WHERE status = 'running'",
        (at,),
    )


def add_attempt(
    conn: sqlite3.Connection, run_id: int, claim_id: str, thread_id: str, at: str
) -> None:
    conn.execute(
        "INSERT INTO attempts (run_id, claim_id, thread_id, started_at)"
        " VALUES (?, ?, ?, ?)",
        (run_id, claim_id, thread_id, at),
    )


def claims_started(conn: sqlite3.Connection, run_id: int) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT claim_id FROM attempts WHERE run_id = ?", (run_id,)
    ).fetchall()
    return {row["claim_id"] for row in rows}


def add_usage(conn: sqlite3.Connection, run_id: int, usage: dict[str, Any]) -> None:
    """Record one model call, given as claim_id, model, input_tokens,
    output_tokens, cost, seconds and recorded_at."""
    conn.execute(
        "INSERT INTO usage (run_id, claim_id, model, input_tokens, output_tokens,"
        " cost, seconds, recorded_at) VALUES (:run_id, :claim_id, :model,"
        " :input_tokens, :output_tokens, :cost, :seconds, :recorded_at)",
        {"run_id": run_id} | usage,
    )


def usage(conn: sqlite3.Connection, run_id: int) -> sqlite3.Row:
    return conn.execute(USAGE, (run_id,)).fetchone()
