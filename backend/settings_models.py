"""The shapes of the platform's settings in the API: the approval limit and
what a round of improvement works to, each change kept with who made it."""

from datetime import datetime

from pydantic import BaseModel, Field

from backend.version_models import ModelAllowed
from settings import setting

# The most claim agents a run may have working at once
MAX_AGENTS = int(setting("MAX_AGENTS"))
# The judge grades from 0 (F) to 3 (A)
TOP_GRADE = 3


class Objectives(BaseModel):
    """The floors a new version must reach on the held-out set."""

    accuracy: float = Field(ge=0, le=1)
    grade: float = Field(ge=0, le=TOP_GRADE)


class Margins(BaseModel):
    """How far each measure must move to count, for the noise, or may move the
    wrong way, for the tolerance: accuracy and the grade as differences, cost
    and time per claim as fractions of the old value."""

    accuracy: float = Field(ge=0)
    grade: float = Field(ge=0)
    cost_per_claim: float = Field(ge=0)
    seconds_per_claim: float = Field(ge=0)


class SettingsIn(BaseModel):
    approval_limit: float = Field(gt=0)
    objectives: Objectives
    noise: Margins
    tolerance: Margins
    # US dollars a round may spend on its improver, evaluations and judge
    spending_limit: float = Field(gt=0)
    # Claim agents at once in a round's evaluations
    agents: int = Field(ge=1, le=MAX_AGENTS)


class PlatformSettings(SettingsIn):
    """One row of the settings' history: the values, and who changed them and
    when; nobody for the first, seeded row."""

    number: int
    changed_by: str | None
    changed_at: datetime


class SettingsView(BaseModel):
    """The settings now, with the models the claim agent may use."""

    settings: PlatformSettings
    models_allowed: list[ModelAllowed]
