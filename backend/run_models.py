"""The shapes of the agent's runs in the API: a run, its to-do list and what its
model calls used."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RunStatus = Literal["running", "finished", "stopped"]
TodoStatus = Literal["pending", "in_progress", "completed", "left_for_handler"]


class Todo(BaseModel):
    content: str = Field(min_length=1)
    status: TodoStatus


class RunIn(BaseModel):
    mode: Literal["queue", "claim"]
    cap: int = Field(ge=1)
    model: str = Field(min_length=1)


class Usage(BaseModel):
    model_calls: int
    input_tokens: int
    output_tokens: int
    cost: float
    seconds: float


class Run(RunIn):
    run_id: int
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None
    summary: str | None
    todos: list[Todo]
    claims_started: list[str]
    usage: Usage


class TodosIn(BaseModel):
    todos: list[Todo]


class FinishIn(BaseModel):
    summary: str


class UsageIn(BaseModel):
    claim_id: str | None
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost: float = Field(ge=0)
    seconds: float = Field(ge=0)
