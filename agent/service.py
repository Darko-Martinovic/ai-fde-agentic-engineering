"""The agent's service: a small web service, the agent's entry point beside the
command line. The backend asks it to start a dispatch, to stop one, and to pick
a claim back up after a handler's review. One dispatch runs at a time, in the
background. In the cloud the agent will run as a service like this. `uv run -m
agent.service` runs it on AGENT_HOST and AGENT_PORT."""

import logging
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import partial
from typing import Annotated, Any, Literal

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from langgraph.checkpoint.base import BaseCheckpointSaver
from pydantic import BaseModel, Field

from agent import api, checkpoints, dispatcher, harness, versions
from agent.connection import Refused
from agent.reports import IN_PROGRESS
from settings import setting

log = logging.getLogger(__name__)

# How the service carries a claim on: given the claim, it reports in a line
Carrier = Callable[[str], str]
# A checkpointer of its own for each claim run, on the service's pool
Savers = Callable[[], BaseCheckpointSaver[Any]]

ALREADY_RUNNING = "A dispatch or an evaluation is already running"
NOTHING_RUNNING = "No dispatch or evaluation is running"
MAX_AGENTS = int(setting("MAX_AGENTS"))
# One run at a time; a handler's request to stop it; and the claims being
# carried on after a review, which a dispatch leaves alone
RUNNING = threading.Lock()
STOP = threading.Event()
RESUMING: set[str] = set()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Keep the process's pool open for as long as the service runs, and mark
    any run a stopped service left running as stopped."""
    with checkpoints.pool() as connections:
        app.state.pool = connections
        api.stop_runs()
        yield


app = FastAPI(title="UnderCover Agent", lifespan=lifespan)
router = APIRouter(prefix="/api")


def savers(request: Request) -> Savers:
    return checkpoints.savers(request.app.state.pool)


def in_background(work: Callable[..., None], *args: Any) -> None:
    """Do work on a thread of its own, so it never waits on a request's
    response and a dispatch never holds up the server."""
    threading.Thread(target=work, args=args, daemon=True).start()


def carrier(new_saver: Annotated[Savers, Depends(savers)]) -> Carrier:
    """Carry claims on as the current version, outside any run, so a run's costs
    are its own. A signed-off claim is only paid, so its model makes no call."""
    return lambda claim_id: harness.carry_on(
        claim_id, None, harness.current_version(), new_saver()
    )


class Accepted(BaseModel):
    claim_id: str


class DispatchIn(BaseModel):
    agents: int = Field(ge=1, le=MAX_AGENTS)


class EvaluationIn(DispatchIn):
    evaluation_set: Literal["evaluation", "held_out"]
    tiny: bool


class Started(BaseModel):
    agents: int


class Stopping(BaseModel):
    stopping: bool


@router.get("/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the agent's service is running."""
    return {"status": "ok"}


@router.post("/dispatches", operation_id="start_dispatch", status_code=202)
def start_dispatch(
    dispatch: DispatchIn,
    new_saver: Annotated[Savers, Depends(savers)],
) -> Started:
    """Start a dispatch of the queue with up to N claim agents at once."""
    begin(dispatch, new_saver)
    return Started(agents=dispatch.agents)


@router.post("/evaluations", operation_id="start_evaluation", status_code=202)
def start_evaluation(
    evaluation: EvaluationIn,
    new_saver: Annotated[Savers, Depends(savers)],
) -> Started:
    """Start an evaluation of a labelled set with up to N claim agents at once."""
    begin(evaluation, new_saver)
    return Started(agents=evaluation.agents)


def begin(start: DispatchIn, new_saver: Savers) -> None:
    """Start a run in the background, or refuse while one runs."""
    if not RUNNING.acquire(blocking=False):
        raise HTTPException(409, ALREADY_RUNNING)
    STOP.clear()
    in_background(work_a_run, start, new_saver)


def create(start: DispatchIn) -> dict[str, Any]:
    """Record the run through the backend, on the current version: an
    evaluation, with its copies, or a dispatch."""
    if isinstance(start, EvaluationIn):
        return api.create_evaluation(start.evaluation_set, start.tiny, start.agents)
    return api.create_dispatch(start.agents)


def work_a_run(start: DispatchIn, new_saver: Savers) -> None:
    """Create the run through the backend and work it with claim agents built
    from the version it records; the dispatcher prints each claim's report as
    it comes. A dispatcher that fails marks the run stopped; either way the
    next start is free to go."""
    try:
        run = create(start)
        version = versions.version(api.get_version(run["version"]))
        work = partial(harness.work_in_run, version=version, new_saver=new_saver)
        dispatcher.work_run(run, work, RESUMING, STOP)
    except Exception:
        log.exception("The run stopped")
        api.stop_runs()
    finally:
        RUNNING.release()


@router.post("/runs/stop", operation_id="stop_run", status_code=202)
def stop_run() -> Stopping:
    """Ask the running dispatch to start no more claims and finish as stopped."""
    if not RUNNING.locked():
        raise HTTPException(409, NOTHING_RUNNING)
    STOP.set()
    return Stopping(stopping=True)


@router.post("/claims/{claim_id}/resume", operation_id="resume_claim", status_code=202)
def resume_claim(
    claim_id: str,
    carry: Annotated[Carrier, Depends(carrier)],
) -> Accepted:
    """Pick a claim back up after a handler's review."""
    try:
        claim = api.get_claim(claim_id)
    except Refused as refused:
        raise HTTPException(refused.status, refused.detail) from refused
    if claim["status"] != IN_PROGRESS:
        raise HTTPException(
            409, f"Claim {claim_id} is {claim['status']}, not in_progress"
        )
    if not claim["decisions"] or claim["decisions"][-1]["review"] is None:
        raise HTTPException(409, f"Claim {claim_id} has no handler's review")
    if claim_id in RESUMING:
        raise HTTPException(409, f"Claim {claim_id} is being picked up already")
    RESUMING.add(claim_id)
    in_background(report, carry, claim_id)
    return Accepted(claim_id=claim_id)


def report(carry: Carrier, claim_id: str) -> None:
    """Carry the claim on and print its report, as the command line does."""
    try:
        print(carry(claim_id), flush=True)
    finally:
        RESUMING.discard(claim_id)


app.include_router(router)


def main() -> None:
    uvicorn.run(
        "agent.service:app",
        host=setting("AGENT_HOST"),
        port=int(setting("AGENT_PORT")),
        reload=setting("AGENT_RELOAD") == "true",
        reload_dirs=["agent"],
    )


if __name__ == "__main__":
    main()
