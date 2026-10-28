"""What the improver reads of a round's results: the current version and its
scores, its mistakes on the evaluation set beside the handlers' decisions, the
earlier rounds and what a round works to. From the held-out set, scores only."""

from pydantic import BaseModel

from backend.round_models import RoundStatus, Scores
from backend.version_models import ModelAllowed


class Answer(BaseModel):
    decision: str | None
    payout: float | None
    reasons: str | None


class HandlersAnswer(BaseModel):
    decision: str
    payout: float
    reason: str
    reference: str


class JudgesGrade(BaseModel):
    grade: float | None
    letter: str | None
    same_grounds: float | None
    same_section: float | None


class BesideHandler(BaseModel):
    """A claim of the evaluation set, the agent's answer beside the handler's,
    with the judge's grade."""

    claim_id: str
    summary: str
    agent: Answer
    handler: HandlersAnswer
    judge: JudgesGrade


class Mistakes(BaseModel):
    """From a version's latest evaluation of the evaluation set: the claims it
    got wrong, and the five right ones it explained least well."""

    wrong: list[BesideHandler]
    explained_least_well: list[BesideHandler]


class CurrentVersion(BaseModel):
    number: int
    instructions: str
    model: str
    reasoning_effort: str


class EarlierRound(BaseModel):
    round_id: int
    recipe_number: int
    status: RoundStatus
    version_tried: int | None
    model: str | None
    reasoning_effort: str | None
    reason: str | None
    verdict: str | None
    verdict_reason: str | None
    held_out_before: Scores | None
    held_out_after: Scores | None


class ImproverView(BaseModel):
    """What the improver reads: the current version and its scores on both
    sets, its mistakes on the evaluation set, the earlier rounds, what the
    round works to, what's left of its spending limit and the models allowed.
    From the held-out set, scores only."""

    current_version: CurrentVersion
    scores: dict[str, Scores | None]
    evaluation_set: Mistakes
    earlier_rounds: list[EarlierRound]
    objectives_on_the_held_out_set: dict[str, float]
    noise: dict[str, float]
    tolerance: dict[str, float]
    rule: str
    spending_left: float
    models_allowed: list[ModelAllowed]
