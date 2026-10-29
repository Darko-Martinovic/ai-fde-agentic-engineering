"""The agent's service: a small web service, the agent's entry point beside the
command line. The backend asks it to start a dispatch, an evaluation or a round
of improvement, to stop a run, to carry a round on after a handler's review of
the improver's proposal, and to pick a claim back up after a handler's review.
One run or round works at a time, in the background; a round waiting for a
handler holds nothing. In the cloud the agent will run as a service like this.
`uv run -m agent.service` runs it on AGENT_HOST and AGENT_PORT."""

import logging
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import partial
from typing import Annotated, Any
from uuid import uuid4

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from langgraph.checkpoint.base import BaseCheckpointSaver

from agent import (
    api,
    checkpoints,
    dispatcher,
    harness,
    improver_api,
    rounds,
    versions,
)
from agent.connection import Refused, require_key
from agent.reports import IN_PROGRESS
from agent.run_lock import RunLock
from agent.service_models import (
    Accepted,
    DispatchIn,
    EvaluationIn,
    ReviewIn,
    Reviewing,
    RoundStarted,
    RoundStartIn,
    Started,
    Stopping,
)
from agent.versions import Model
from settings import setting

log = logging.getLogger(__name__)

# How the service carries a claim on: given the claim, it reports in a line
Carrier = Callable[[str], str]
# A checkpointer of its own for each claim run, on the service's pool
Savers = Callable[[], BaseCheckpointSaver[Any]]

NOTHING_RUNNING = "No dispatch or evaluation is running"


# One run or round at a time; a handler's request to stop a run; and the claims
# being carried on after a review, which a dispatch leaves alone
RUNNING = RunLock()
STOP = threading.Event()
RESUMING: set[str] = set()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Keep the process's pool open for as long as the service runs, and mark
    any run a stopped service left running as stopped, and any round, unless
    it waits for a handler: its proposal is in the backend and the improver's
    progress is saved, so a review carries it on."""
    require_key()
    with checkpoints.pool() as connections:
        app.state.pool = connections
        api.stop_runs()
        improver_api.stop_rounds()
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
    """Start a run in the background, or refuse while one works."""
    kind = "An evaluation" if isinstance(start, EvaluationIn) else "A dispatch"
    RUNNING.take(f"{kind} is running")
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


def round_workers(new_saver: Annotated[Savers, Depends(savers)]) -> rounds.RoundWorkers:
    """How a round works: the improver on the model the round names, with a
    saver of its own, and each evaluation through the dispatcher, with claim
    agents built from the version it records."""

    def evaluate(run: dict[str, Any]) -> None:
        version = versions.version(api.get_version(run["version"]))
        work = partial(harness.work_in_run, version=version, new_saver=new_saver)
        dispatcher.work_run(run, work, RESUMING, STOP)

    return rounds.RoundWorkers(
        model_for=lambda model: harness.chat_model(
            Model(
                name=model["model"],
                provider=model["provider"],
                options=model["options"],
            )
        ),
        new_saver=new_saver,
        evaluate=evaluate,
    )


Workers = Annotated[rounds.RoundWorkers, Depends(round_workers)]


def or_let_go[T](record: Callable[[], T]) -> T:
    """Record something through the backend while holding the lock, letting go
    of it, and passing the backend's refusal on, when that fails."""
    try:
        return record()
    except Refused as refused:
        RUNNING.release()
        raise HTTPException(refused.status, refused.detail) from refused
    except Exception:
        RUNNING.release()
        raise


def holding(work: Callable[..., None], *args: Any) -> None:
    """Do a round's work, letting go of the lock when it pauses for a handler
    or ends."""
    try:
        work(*args)
    finally:
        RUNNING.release()


@router.post("/rounds", operation_id="start_round", status_code=202)
def start_round(start: RoundStartIn, workers: Workers) -> RoundStarted:
    """Start a round of improvement: its first evaluations, then the improver."""
    RUNNING.take("A round is starting", round_=True)
    thread_id = f"improver-{uuid4().hex[:8]}"
    worked = or_let_go(lambda: improver_api.create_round(start.handler_id, thread_id))
    RUNNING.holder = f"Round {worked['round_id']} is running"
    STOP.clear()
    in_background(holding, rounds.work_round, worked, workers)
    return RoundStarted(round_id=worked["round_id"])


@router.post(
    "/rounds/{round_id}/proposals/{proposal_id}/review",
    operation_id="review_proposal",
    status_code=202,
)
def review_proposal(
    round_id: int, proposal_id: int, review: ReviewIn, workers: Workers
) -> Reviewing:
    """Record a handler's review of the improver's proposal and carry the round on."""
    RUNNING.take(f"Round {round_id} is running", round_=True)
    or_let_go(
        lambda: improver_api.record_review(round_id, proposal_id, review.model_dump())
    )
    STOP.clear()
    in_background(
        holding, rounds.resume_round, round_id, review.approved, review.note, workers
    )
    return Reviewing(round_id=round_id, proposal_id=proposal_id)


@router.post("/runs/stop", operation_id="stop_run", status_code=202)
def stop_run() -> Stopping:
    """Ask the running dispatch to start no more claims and finish as stopped."""
    if not RUNNING.locked():
        raise HTTPException(409, NOTHING_RUNNING)
    if RUNNING.round:
        raise HTTPException(409, f"{RUNNING.holder}: stop it on the Improvement page")
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
