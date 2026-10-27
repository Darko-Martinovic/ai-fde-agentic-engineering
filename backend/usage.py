"""What the claim agents' work costs, recorded on each claim: the tokens and cost
of each model call, and the time of each spell of work, with the run it
happened in, or none."""

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import Connection

from backend.api import Db, found, load_claim, now
from backend.store import runs, usage
from backend.usage_models import ModelCall, ModelCallIn, WorkTime, WorkTimeIn

router = APIRouter(prefix="/api/claims/{claim_id}")


def require_started(conn: Connection, claim_id: str) -> None:
    """A claim's costs belong to work on it: refuse a claim never started."""
    if load_claim(conn, claim_id).attempts == 0:
        raise HTTPException(409, f"Claim {claim_id} has not been started")


def require_run(conn: Connection, run_id: int | None) -> None:
    """Refuse a run that doesn't exist; None is work outside any run."""
    if run_id is not None:
        found(runs.run(conn, run_id), "Run", str(run_id))


@router.post("/model-calls", operation_id="record_model_call")
def record_model_call(claim_id: str, call: ModelCallIn, conn: Db) -> ModelCall:
    """Record one model call on a claim: its tokens, cost and time."""
    require_started(conn, claim_id)
    require_run(conn, call.run_id)
    row = call.model_dump() | {"recorded_at": now()}
    usage.add_model_call(conn, claim_id, row)
    return ModelCall.model_validate(row | {"claim_id": claim_id})


@router.post("/work-times", operation_id="record_work_time")
def record_work_time(claim_id: str, spell: WorkTimeIn, conn: Db) -> WorkTime:
    """Record one spell of the agent's work on a claim, which ended now."""
    require_started(conn, claim_id)
    require_run(conn, spell.run_id)
    started = datetime.fromisoformat(now()) - timedelta(seconds=spell.seconds)
    row = spell.model_dump() | {"started_at": started.isoformat()}
    usage.add_work_time(conn, claim_id, row)
    return WorkTime.model_validate(row | {"claim_id": claim_id})
