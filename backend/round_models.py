"""The shapes of rounds of improvement in the API: a round and where it has got
to, the improver's proposals and their reviews, a recipe, the scores a version
is judged on and the verdict, and what the improver sees."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.diffs import Hunk
from backend.run_models import EvaluationSet
from backend.version_models import ModelAllowed


class Stage(StrEnum):
    FIRST_EVALUATIONS = "first_evaluations"
    IMPROVING = "improving"
    CHANGE_WAITING = "change_waiting"
    EVALUATING = "evaluating"
    VERDICT = "verdict"
    RECIPE_WAITING = "recipe_waiting"
    FINISHED = "finished"
    STOPPED = "stopped"


class RoundStatus(StrEnum):
    OPEN = "open"
    FINISHED = "finished"
    STOPPED = "stopped"


class ProposalKind(StrEnum):
    CHANGE = "change"
    RECIPE = "recipe"


class Scores(BaseModel):
    """What a version scored on a set, on average over its runs there."""

    accuracy: float
    grade: float | None
    cost_per_claim: float
    seconds_per_claim: float


class RoundIn(BaseModel):
    """A round to start, as the agent's service records it: the handler who
    started it and the improver's thread."""

    handler_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)


class ChangeIn(BaseModel):
    """A new version of the claim agent's configuration, as proposed."""

    instructions: str = Field(min_length=1)
    model: str = Field(min_length=1)
    reasoning_effort: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class RecipeIn(BaseModel):
    recipe: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ReviewIn(BaseModel):
    """A handler's review of a proposal, as the agent's service records it."""

    handler_id: str = Field(min_length=1)
    approved: bool
    note: str


class RejectionIn(BaseModel):
    """A handler's rejection of a proposal, with what's wrong."""

    note: str = Field(min_length=1)


class RoundEvaluationIn(BaseModel):
    evaluation_set: EvaluationSet


class FinishRoundIn(BaseModel):
    """How a round ends: finished, or stopped by what went wrong."""

    stopped: bool
    reason: str


class ImproverCallIn(BaseModel):
    model: str = Field(min_length=1)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost: float = Field(ge=0)
    seconds: float = Field(ge=0)


class ImproverCall(ImproverCallIn):
    round_id: int
    recorded_at: datetime


class Proposal(BaseModel):
    proposal_id: int
    round_id: int
    kind: ProposalKind
    proposed: dict[str, Any]
    reason: str
    proposed_at: datetime
    review: Literal["approved", "rejected"] | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None


class ProposalView(Proposal):
    """A proposal beside what it would change: for a change, the lines of the
    instructions and the model and reasoning effort before it, against the
    version the round started from; for a recipe, the lines of the recipe the
    round follows."""

    changes: list[Hunk]
    model_before: str | None
    reasoning_effort_before: str | None


class Recipe(BaseModel):
    number: int
    recipe: str
    based_on: int | None
    reason: str
    proposed_by: str
    round_id: int | None
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime


class RecipeDetails(Recipe):
    changes: list[Hunk]


class Progress(BaseModel):
    """How far a stage with steps has got: the step underway, of how many."""

    step: int
    of: int


class Round(BaseModel):
    """A round as it stands: its records, where it has got to, what it has
    spent of its limit, and its waiting proposal, if it has one."""

    round_id: int
    started_by: str
    started_at: datetime
    settings_number: int
    recipe_number: int
    version_before: int
    improver_model: str
    thread_id: str
    first_evaluations: list[EvaluationSet]
    status: RoundStatus
    stopped_by: str | None
    stop_reason: str | None
    finished_at: datetime | None
    version_tried: int | None
    verdict: str | None
    verdict_reason: str | None
    scores_before: Scores | None
    scores_after: Scores | None
    stage: Stage
    progress: Progress | None
    spent: float
    spending_limit: float
    # Every proposal, oldest first, and the one waiting for a handler, if any,
    # beside what it would change
    proposals: list[Proposal]
    waiting: ProposalView | None


class Verdict(BaseModel):
    """What the backend decided on the version a round tried, and why."""

    version: int
    kept: bool
    why: str
    current_version: int
    held_out_before: Scores | None
    held_out_after: Scores | None
    evaluation_after: Scores | None


class Stopped(BaseModel):
    round_ids: list[int]


class ImproverModel(BaseModel):
    """The model the improver runs on and how to build it, its reasoning
    effort among its options unless it runs with none of its own."""

    model: str
    provider: str
    options: dict[str, Any]


class RoundWork(Round):
    """A round as the improver works it: its instructions, with the recipe the
    round follows, its model, and the models a change may use."""

    instructions: str
    improver: ImproverModel
    models_allowed: list[ModelAllowed]


class Improvement(BaseModel):
    """The rounds so far, newest first, and the recipe's versions."""

    rounds: list[Round]
    recipes: list[Recipe]
    current_recipe: int


class RoundStarted(BaseModel):
    round_id: int


class Reviewing(BaseModel):
    round_id: int
    proposal_id: int
