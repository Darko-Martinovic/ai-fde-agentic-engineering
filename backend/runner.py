"""Starting and stopping the UnderCover Agent, one run at a time."""

import multiprocessing
import sqlite3
from multiprocessing.process import BaseProcess
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from agent.__main__ import main as work
from agent.config import current_model, model, models
from backend.api import Db, load_claim, now
from backend.store import claims, runs

router = APIRouter(prefix="/api/agent")


class AgentState(BaseModel):
    model: str | None
    running: bool
    mode: Literal["claim", "queue"] | None
    claim_id: str | None


class ModelChoice(BaseModel):
    spec: str
    label: str
    default: bool


class RunClaimIn(BaseModel):
    model: str

    @field_validator("model")
    @classmethod
    def model_is_allowed(cls, spec: str) -> str:
        """Only a model in models.toml runs."""
        return model(spec).spec


class RunQueueIn(RunClaimIn):
    cap: int = Field(ge=1)


class Run:
    """The agent's process, run apart from the backend so Stop ends it at once."""

    process: BaseProcess | None = None
    mode: Literal["claim", "queue"] | None = None
    model: str | None = None


RUN = Run()


def start_process(arguments: list[str]) -> BaseProcess:
    """Start the agent's command line, with these arguments, in a process of its
    own."""
    process = multiprocessing.get_context("spawn").Process(
        target=work, args=(arguments,), daemon=True
    )
    process.start()
    return process


def running() -> bool:
    return RUN.process is not None and RUN.process.is_alive()


def state(conn: sqlite3.Connection) -> AgentState:
    if not running():
        return AgentState(model=None, running=False, mode=None, claim_id=None)
    return AgentState(
        model=RUN.model,
        running=True,
        mode=RUN.mode,
        claim_id=claims.first_in_progress(conn),
    )


def return_to_queue(conn: sqlite3.Connection) -> None:
    """Put claims left in progress back to waiting, clearing unpaid decisions,
    and mark any run still running as stopped."""
    with conn:
        claims.return_to_queue(conn)
        runs.stop_running(conn, now())


def launch(
    conn: sqlite3.Connection,
    mode: Literal["claim", "queue"],
    spec: str,
    arguments: list[str],
) -> None:
    """Start a run on a model, first returning any claim an earlier run left in
    progress."""
    if running():
        raise HTTPException(409, "The agent is already running")
    return_to_queue(conn)
    RUN.process = start_process([*arguments, "--model", spec])
    RUN.mode = mode
    RUN.model = model(spec).label


@router.get("", operation_id="get_agent")
def get_agent(conn: Db) -> AgentState:
    """Say whether the agent is running, and on which claim."""
    return state(conn)


@router.get("/models", operation_id="list_models")
def list_models() -> list[ModelChoice]:
    """List the models the agent may run on, marking the default (MODEL_NAME)."""
    default = current_model().spec
    return [
        ModelChoice(spec=m.spec, label=m.label, default=m.spec == default)
        for m in models().values()
    ]


@router.post("/claims/{claim_id}", operation_id="run_claim")
def run_claim(claim_id: str, run: RunClaimIn, conn: Db) -> AgentState:
    """Start the agent on one waiting claim, on a model."""
    claim = load_claim(conn, claim_id)
    if claim.status != "waiting":
        raise HTTPException(409, f"Claim {claim_id} is {claim.status}, not waiting")
    launch(conn, "claim", run.model, [claim_id])
    return state(conn)


@router.post("/queue", operation_id="run_queue")
def run_queue(run: RunQueueIn, conn: Db) -> AgentState:
    """Start the queue agent on up to `cap` waiting claims, on a model."""
    if claims.count_in(conn, "waiting") == 0:
        raise HTTPException(409, "No claims are waiting")
    launch(conn, "queue", run.model, ["--cap", str(run.cap)])
    return state(conn)


@router.post("/stop", operation_id="stop_agent")
def stop_agent(conn: Db) -> AgentState:
    """Stop the agent and put any claim in progress back to waiting, with its steps."""
    if RUN.process is not None:
        RUN.process.terminate()
        RUN.process.join(timeout=10)
    RUN.process = None
    RUN.mode = None
    RUN.model = None
    return_to_queue(conn)
    return state(conn)
