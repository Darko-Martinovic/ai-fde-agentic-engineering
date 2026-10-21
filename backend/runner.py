"""Starting and stopping the UnderCover Agent, one run at a time."""

import multiprocessing
import sqlite3
from multiprocessing.process import BaseProcess
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.__main__ import main as work
from agent.config import current_model
from backend.api import Db, load_claim, now
from backend.store import claims, runs

router = APIRouter(prefix="/api/agent")


class AgentState(BaseModel):
    model: str
    running: bool
    mode: Literal["claim", "queue"] | None
    claim_id: str | None


class Run:
    """The agent's process, run apart from the backend so Stop ends it at once."""

    process: BaseProcess | None = None
    mode: Literal["claim", "queue"] | None = None


RUN = Run()


def start_process(claim_ids: list[str]) -> BaseProcess:
    """Start the agent on the claims given, or on the whole queue if none are."""
    process = multiprocessing.get_context("spawn").Process(
        target=work, args=(claim_ids,), daemon=True
    )
    process.start()
    return process


def running() -> bool:
    return RUN.process is not None and RUN.process.is_alive()


def state(conn: sqlite3.Connection) -> AgentState:
    model = current_model().label
    if not running():
        return AgentState(model=model, running=False, mode=None, claim_id=None)
    return AgentState(
        model=model,
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
    conn: sqlite3.Connection, mode: Literal["claim", "queue"], claim_ids: list[str]
) -> None:
    """Start a run, first returning any claim an earlier run left in progress."""
    if running():
        raise HTTPException(409, "The agent is already running")
    return_to_queue(conn)
    RUN.process = start_process(claim_ids)
    RUN.mode = mode


@router.get("", operation_id="get_agent")
def get_agent(conn: Db) -> AgentState:
    """Say whether the agent is running, and on which claim."""
    return state(conn)


@router.post("/claims/{claim_id}", operation_id="run_claim")
def run_claim(claim_id: str, conn: Db) -> AgentState:
    """Start the agent on one waiting claim."""
    claim = load_claim(conn, claim_id)
    if claim.status != "waiting":
        raise HTTPException(409, f"Claim {claim_id} is {claim.status}, not waiting")
    launch(conn, "claim", [claim_id])
    return state(conn)


@router.post("/queue", operation_id="run_queue")
def run_queue(conn: Db) -> AgentState:
    """Start the agent on every waiting claim, in turn."""
    if claims.count_in(conn, "waiting") == 0:
        raise HTTPException(409, "No claims are waiting")
    launch(conn, "queue", [])
    return state(conn)


@router.post("/stop", operation_id="stop_agent")
def stop_agent(conn: Db) -> AgentState:
    """Stop the agent and put any claim in progress back to waiting, with its steps."""
    if RUN.process is not None:
        RUN.process.terminate()
        RUN.process.join(timeout=10)
    RUN.process = None
    RUN.mode = None
    return_to_queue(conn)
    return state(conn)
