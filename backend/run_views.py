"""A run as the API shows it: its claims with their lines in the queue and their
work in the run, what its model calls used, and its time, and what a dispatch
left when it finished."""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import Connection, RowMapping

from backend.api import found, queue_line
from backend.models import ClaimSummary
from backend.run_models import Held, Run, RunClaim, Summary
from backend.store import claims, runs, usage

# The states in which a claim waits for the next dispatch
UNFINISHED = ("in_progress", "waiting")


def run_claims(conn: Connection, run_id: int) -> list[RunClaim]:
    """A run's claims, in its order, each with its work in the run."""
    lines = {line.claim_id: line for line in map(queue_line, claims.queue(conn))}
    costs = usage.claim_costs(conn, run_id)
    times = usage.claim_times(conn, run_id)
    return [
        run_claim(lines[claim_id], times.get(claim_id), costs.get(claim_id, 0))
        for claim_id in runs.claims_of(conn, run_id)
    ]


def run_claim(
    line: ClaimSummary, spells: RowMapping | None, model_cost: float
) -> RunClaim:
    """A claim's line in the queue, with its spells of work and their cost."""
    return RunClaim.model_validate(
        line.model_dump()
        | {
            "started_at": spells["started_at"] if spells else None,
            "seconds": spells["seconds"] if spells else 0,
            "model_cost": model_cost,
        }
    )


def load_run(conn: Connection, run_id: int) -> Run:
    """Load one run with its claims, its usage and, once it ends, its time."""
    row = found(runs.run(conn, run_id), "Run", str(run_id))
    finished = row["finished_at"]
    seconds = (
        datetime.fromisoformat(finished) - datetime.fromisoformat(row["started_at"])
        if finished
        else None
    )
    return Run.model_validate(
        dict(row)
        | {
            "seconds": seconds.total_seconds() if seconds else None,
            "summary": row["summary"] and Summary.model_validate_json(row["summary"]),
            "usage": dict(usage.run_model_calls(conn, run_id)),
            "claims": run_claims(conn, run_id),
        }
    )


def require_running(conn: Connection, run_id: int) -> Run:
    """Load a run that is still running, or refuse."""
    run = load_run(conn, run_id)
    if run.status != "running":
        raise HTTPException(409, f"Run {run_id} is {run.status}, not running")
    return run


def summary(worked: list[RunClaim]) -> Summary:
    """What a dispatch left, each claim counted once, from where it stands."""
    decided = [c for c in worked if c.status in ("decided", "awaiting_sign_off")]
    return Summary(
        approved=sum(c.decision == "approve" for c in decided),
        declined=sum(c.decision == "decline" for c in decided),
        referred=sum(c.status == "referred" for c in worked),
        waiting_for_sign_off=[
            Held(claim_id=c.claim_id, payout=c.payout or 0)
            for c in worked
            if c.status == "awaiting_sign_off"
        ],
        left_for_handler=[c.claim_id for c in worked if c.status == "left_for_handler"],
        unfinished=[c.claim_id for c in worked if c.status in UNFINISHED],
    )
