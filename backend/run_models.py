"""The shapes of the agent's runs in the API: a dispatch, its claims, what its
model calls used, and its summary once it finishes."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from backend.models import ClaimSummary
from settings import setting

RunStatus = Literal["running", "finished", "stopped"]
RunKind = Literal["dispatch"]
# The most claim agents a run may have working at once
MAX_AGENTS = int(setting("MAX_AGENTS"))


class DispatchIn(BaseModel):
    agents: int = Field(ge=1, le=MAX_AGENTS)
    model: str = Field(min_length=1)
    reasoning_effort: str = Field(min_length=1)


class RunClaimsIn(BaseModel):
    claim_ids: list[str]


class FinishIn(BaseModel):
    # Whether the run stopped partway, as when a handler pressed Stop
    stopped: bool


class Usage(BaseModel):
    model_calls: int
    input_tokens: int
    output_tokens: int
    cost: float


class Held(BaseModel):
    claim_id: str
    payout: float


class Summary(BaseModel):
    """What a dispatch left, from the records when it finished, each claim
    counted once: an approval held for sign-off counts as approved, and a claim
    in progress or back in the queue is unfinished, for the next dispatch."""

    approved: int
    declined: int
    referred: int
    waiting_for_sign_off: list[Held]
    left_for_handler: list[str]
    unfinished: list[str]


class RunClaim(ClaimSummary):
    """A run's claim as the queue shows it, with its work in this run: when its
    first spell started, its seconds and its model calls' cost."""

    started_at: datetime | None
    seconds: float
    model_cost: float


class Run(BaseModel):
    run_id: int
    kind: RunKind
    agents: int
    model: str
    reasoning_effort: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None
    # From its start to its finish, once it has finished
    seconds: float | None
    summary: Summary | None
    usage: Usage
    claims: list[RunClaim]


class Stopped(BaseModel):
    run_ids: list[int]
