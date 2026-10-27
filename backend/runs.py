"""The agent's runs. The dashboard starts a dispatch and stops a run through the
backend, which asks the agent's service and writes nothing itself. The service
records each dispatch under /api/runs: its start, its claims in order, and its
finish, when the backend builds its summary from its records. The dashboard
reads the latest under /api/dispatches."""

from fastapi import APIRouter, HTTPException

from backend import agent_service
from backend.api import Db, now
from backend.run_models import (
    DispatchIn,
    DispatchStart,
    FinishIn,
    Run,
    RunClaimsIn,
    Started,
    Stopped,
    Stopping,
)
from backend.run_views import load_run, require_running, run_claims, summary
from backend.store import claims, runs

router = APIRouter(prefix="/api")


@router.post("/dispatches", operation_id="start_dispatch", status_code=202)
def start_dispatch(dispatch: DispatchStart) -> Started:
    """Ask the agent's service to start a dispatch with N claim agents at once."""
    return Started.model_validate(
        agent_service.start_dispatch(dispatch.agents, dispatch.model)
    )


@router.post("/runs/stop-request", operation_id="stop_run", status_code=202)
def stop_run() -> Stopping:
    """Ask the agent's service to stop the run it's working, starting no more claims."""
    return Stopping.model_validate(agent_service.stop_run())


@router.post("/runs/dispatches", operation_id="create_dispatch")
def create_dispatch(dispatch: DispatchIn, conn: Db) -> Run:
    """Record a new dispatch, running, with N claim agents at once on a model."""
    started = dispatch.model_dump() | {"kind": "dispatch", "started_at": now()}
    return load_run(conn, runs.add(conn, started))


@router.put("/runs/{run_id}/claims", operation_id="record_run_claims")
def record_run_claims(run_id: int, listed: RunClaimsIn, conn: Db) -> Run:
    """Record the claims a running dispatch works, in the order it takes them."""
    require_running(conn, run_id)
    for claim_id in listed.claim_ids:
        if claims.claim(conn, claim_id) is None:
            raise HTTPException(404, f"Claim {claim_id} not found")
    runs.set_claims(conn, run_id, listed.claim_ids)
    return load_run(conn, run_id)


@router.post("/runs/{run_id}/finish", operation_id="finish_run")
def finish_run(run_id: int, finish: FinishIn, conn: Db) -> Run:
    """Finish a running run, or mark it stopped, with a dispatch's summary."""
    require_running(conn, run_id)
    left = summary(run_claims(conn, run_id)).model_dump_json()
    status = "stopped" if finish.stopped else "finished"
    runs.finish(conn, run_id, status, left, now())
    return load_run(conn, run_id)


@router.post("/runs/stop-all", operation_id="stop_runs")
def stop_runs(conn: Db) -> Stopped:
    """Mark every run still running as stopped, as when the agent's service starts."""
    return Stopped(run_ids=runs.stop_running(conn, now()))


@router.get("/dispatches/latest", operation_id="get_latest_dispatch")
def get_latest_dispatch(conn: Db) -> Run | None:
    """Get the newest dispatch with its claims, cost and time, or nothing yet."""
    run_id = runs.latest(conn, "dispatch")
    return load_run(conn, run_id) if run_id else None
