"""The shapes of the agent's runs in the API: a dispatch, its claims, what its
model calls used, and its summary once it finishes."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from agent.config import model
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
    agents: int = Field(ge=1, le=MAX_AGENTS)
    model: str = Field(min_length=1)
    reasoning_effort: str = Field(min_length=1)


class DispatchStart(BaseModel):
    agents: int = Field(ge=1, le=MAX_AGENTS)
    model: str

    @field_validator("model")
    @classmethod
    def model_is_allowed(cls, spec: str) -> str:
        """Only a model in models.toml runs."""
        return model(spec).spec


class EvaluationIn(DispatchIn):
    evaluation_set: EvaluationSet
    # Only the set's five tiny claims, for a quick evaluation
    tiny: bool


class EvaluationStart(DispatchStart):
    evaluation_set: EvaluationSet
    tiny: bool


class Started(BaseModel):
    agents: int
    model: str


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


class EvaluationClaim(RunClaim):
    """An evaluation's copy, its agent's decision beside the handler's on the
    claim it copies: whether it's right, and what a mistake costs."""

    copy_of: str
    reasons: str | None
    handler_decision: str
    handler_payout: float
    right: bool
    mistake_cost: float


class Evaluation(RunFacts):
    """An evaluation with its measures and its copies, each beside the
    handler's decision."""

    measures: Measures
    claims: list[EvaluationClaim]


class Stopped(BaseModel):
    run_ids: list[int]
