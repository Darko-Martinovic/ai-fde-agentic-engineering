"""The agent's runs: each run's cap and model, its to-do list, its summary, and
what its model calls used."""

import json

from fastapi import APIRouter

from backend.api import Db, load_run, now, require_running
from backend.models import FinishIn, Run, RunIn, TodosIn, UsageIn
from backend.store import runs

router = APIRouter(prefix="/api/runs")


@router.post("", operation_id="start_run")
def start_run(run: RunIn, conn: Db) -> Run:
    """Start a run of the agent on a model, capped at a number of claims."""
    with conn:
        run_id = runs.add(conn, run.model_dump() | {"started_at": now()})
    return load_run(conn, run_id)


@router.get("/latest", operation_id="get_latest_run")
def get_latest_run(conn: Db) -> Run | None:
    """Get the latest run, or nothing before the first."""
    run_id = runs.latest(conn)
    return load_run(conn, run_id) if run_id else None


@router.put("/{run_id}/todos", operation_id="write_todos")
def write_todos(run_id: int, todos: TodosIn, conn: Db) -> Run:
    """Replace a running run's to-do list."""
    require_running(conn, run_id)
    with conn:
        runs.set_todos(conn, run_id, json.dumps(todos.model_dump()["todos"]))
    return load_run(conn, run_id)


@router.post("/{run_id}/finish", operation_id="finish_run")
def finish_run(run_id: int, finish: FinishIn, conn: Db) -> Run:
    """Finish a running run with its summary for the handlers."""
    require_running(conn, run_id)
    with conn:
        runs.finish(conn, run_id, "finished", finish.summary, now())
    return load_run(conn, run_id)


@router.post("/{run_id}/usage", operation_id="record_usage")
def record_usage(run_id: int, usage: UsageIn, conn: Db) -> Run:
    """Record what one model call in a run used: tokens, cost and time."""
    load_run(conn, run_id)
    with conn:
        runs.add_usage(conn, run_id, usage.model_dump() | {"recorded_at": now()})
    return load_run(conn, run_id)
