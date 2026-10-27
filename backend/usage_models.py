"""The shapes of what the claim agents' work costs in the API: a model call and a
spell of work on a claim, each with the run it happened in, or none."""

from datetime import datetime

from pydantic import BaseModel, Field


class ModelCallIn(BaseModel):
    thread_id: str = Field(min_length=1)
    run_id: int | None
    model: str = Field(min_length=1)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost: float = Field(ge=0)
    seconds: float = Field(ge=0)


class ModelCall(ModelCallIn):
    claim_id: str
    recorded_at: datetime


class WorkTimeIn(BaseModel):
    thread_id: str = Field(min_length=1)
    run_id: int | None
    seconds: float = Field(ge=0)


class WorkTime(WorkTimeIn):
    claim_id: str
    started_at: datetime
