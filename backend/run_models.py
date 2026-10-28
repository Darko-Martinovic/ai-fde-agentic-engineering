"""The shapes of the agent's runs in the API: a dispatch, its claims, what its
model calls used, and its summary once it finishes."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from backend.models import ClaimSummary
from settings import setting

RunStatus = Literal["running", "finished", "stopped"]
RunKind = Literal["dispatch", "evaluation"]
DISPATCH, EVALUATION = "dispatch", "evaluation"
# The labelled sets an evaluation works copies of: the queue's own claims, or
# the held-out ones
EvaluationSet = Literal["evaluation", "held_out"]
# The most claim agents a run may have working at once
MAX_AGENTS = int(setting("MAX_AGENTS"))


class DispatchIn(BaseModel):
    """A dispatch or an evaluation to start or record: N claim agents at once,
    on the current version of the claim agent's configuration."""

    agents: int = Field(ge=1, le=MAX_AGENTS)


class EvaluationIn(DispatchIn):
    evaluation_set: EvaluationSet
    # Only the set's five tiny claims, for a quick evaluation
    tiny: bool


class Started(BaseModel):
    agents: int


class Stopping(BaseModel):
    stopping: bool


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


class RunFacts(BaseModel):
    """What every run shows, apart from its claims."""

    run_id: int
    kind: RunKind
    agents: int
    # The version of the claim agent's configuration it used, and its model
    version: int
    model: str
    reasoning_effort: str
    # For an evaluation: its set, and whether it's the five tiny claims
    evaluation_set: EvaluationSet | None
    tiny: bool | None
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None
    # From its start to its finish, once it has finished
    seconds: float | None
    summary: Summary | None
    usage: Usage


class Run(RunFacts):
    claims: list[RunClaim]


class Measures(BaseModel):
    decision_accuracy: float
    accuracy: float
    cost_of_mistakes: float
    straight_through: float
    model_cost_per_claim: float
    seconds_per_claim: float
    # From its start to its finish, once it has finished
    run_seconds: float | None
    # The judge's average grade from 0 (F) to 3 (A) over the copies it graded,
    # none with none graded, and what its grading cost, apart from the agents'
    grade: float | None
    judge_cost: float


class EvaluationClaim(RunClaim):
    """An evaluation's copy, its agent's decision beside the handler's on the
    claim it copies: whether it's right, and what a mistake costs."""

    copy_of: str
    reasons: str | None
    handler_decision: str
    handler_payout: float
    right: bool
    mistake_cost: float
    # The judge's grade on the agent's explanation, its most likely level and
    # the probability of each check, or none when it couldn't grade it
    grade: float | None
    letter: str | None
    same_grounds: float | None
    same_section: float | None
    judge_cost: float


class Evaluation(RunFacts):
    """An evaluation with its measures and its copies, each beside the
    handler's decision."""

    measures: Measures
    claims: list[EvaluationClaim]


@dataclass(frozen=True)
class Grade:
    """The judge's grade on a copy: its score from 0 (F) to 3 (A), its most
    likely level as a letter, never the score rounded, the probability of each
    check, and what the call cost."""

    grade: float
    letter: str
    same_grounds: float
    same_section: float
    judge_cost: float


class Stopped(BaseModel):
    run_ids: list[int]
