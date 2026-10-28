"""What the agent's service is asked and answers, as the backend calls it."""

from typing import Literal

from pydantic import BaseModel, Field

from settings import setting

MAX_AGENTS = int(setting("MAX_AGENTS"))


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


class RoundStartIn(BaseModel):
    handler_id: str


class ReviewIn(RoundStartIn):
    approved: bool
    note: str


class RoundStarted(BaseModel):
    round_id: int


class Reviewing(BaseModel):
    round_id: int
    proposal_id: int
