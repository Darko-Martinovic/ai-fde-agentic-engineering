"""The agent's service: a small web service, the agent's entry point beside the
command line, which the backend asks to pick a claim back up after a handler's
review. In the cloud the agent will run as a service like this. `uv run -m
agent.service` runs it on AGENT_HOST and AGENT_PORT."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated

import uvicorn
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from agent import api, checkpoints, harness
from agent.config import current_model
from settings import setting

# How the service carries a claim on: given the claim and the run its model
# calls count on, it reports in a line
Carrier = Callable[[str, int], str]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Keep the checkpointer open for as long as the service runs."""
    with checkpoints.saver() as saver:
        app.state.saver = saver
        yield


app = FastAPI(title="UnderCover Agent", lifespan=lifespan)
router = APIRouter(prefix="/api")


def carrier(request: Request) -> Carrier:
    """Carry claims on on the default model, with the service's checkpointer. A
    signed-off claim is only paid, so its model makes no call."""
    saver = request.app.state.saver
    return lambda claim_id, run_id: harness.carry_on(
        claim_id, run_id, current_model(), saver
    )


class Accepted(BaseModel):
    claim_id: str


@router.get("/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the agent's service is running."""
    return {"status": "ok"}


@router.post("/claims/{claim_id}/resume", operation_id="resume_claim", status_code=202)
def resume_claim(
    claim_id: str,
    carry: Annotated[Carrier, Depends(carrier)],
    background: BackgroundTasks,
) -> Accepted:
    """Pick a claim back up after a handler's review."""
    try:
        claim = api.get_claim(claim_id)
    except api.Refused as refused:
        raise HTTPException(refused.status, refused.detail) from refused
    if claim["status"] != "in_progress":
        raise HTTPException(
            409, f"Claim {claim_id} is {claim['status']}, not in_progress"
        )
    if not claim["decisions"] or claim["decisions"][-1]["review"] is None:
        raise HTTPException(409, f"Claim {claim_id} has no handler's review")
    background.add_task(report, carry, claim_id, claim["run_id"])
    return Accepted(claim_id=claim_id)


def report(carry: Carrier, claim_id: str, run_id: int) -> None:
    """Carry the claim on and print its report, as the command line does."""
    print(carry(claim_id, run_id), flush=True)


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
