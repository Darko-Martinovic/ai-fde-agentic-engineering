"""The shapes of the claim agent's configuration in the API: its versions, the
models it may use, and what a version changed from the one before."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from backend.diffs import Hunk

# A model run with no reasoning effort of its own, as a free model is
NO_EFFORT = "default"
CLAIMS_TEAM = "The claims team"


class VersionStatus(StrEnum):
    CURRENT = "current"
    KEPT = "kept"
    UNDER_TEST = "under_test"
    ROLLED_BACK = "rolled_back"


class Verdict(StrEnum):
    KEPT = "kept"
    ROLLED_BACK = "rolled_back"


class ModelAllowed(BaseModel):
    """A model the claim agent may use, with its reasoning efforts, its prices in
    US dollars per million tokens, and the options it's built with."""

    model: str
    label: str
    provider: str
    reasoning_efforts: list[str]
    input_price: float
    output_price: float
    options: dict[str, Any]


class VersionConfig(BaseModel):
    """What the claim agent runs as: its instructions, its model and reasoning
    effort, and how to build the model, its reasoning effort among its options
    unless it runs with none of its own. No scores."""

    number: int
    instructions: str
    model: str
    reasoning_effort: str
    provider: str
    options: dict[str, Any]


class Version(BaseModel):
    number: int
    model: str
    reasoning_effort: str
    based_on: int | None
    reason: str
    proposed_by: str
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime
    verdict: Verdict | None
    verdict_reason: str | None
    status: VersionStatus
    lines_added: int
    lines_removed: int


class VersionDetails(Version):
    instructions: str
    # What it changed from the version it was based on
    based_on_model: str | None
    based_on_reasoning_effort: str | None
    changes: list[Hunk]


class Configuration(BaseModel):
    current: int
    versions: list[Version]
    models_allowed: list[ModelAllowed]
