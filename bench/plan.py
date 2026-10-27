"""The comparison's plan, from bench/plan.toml, and what it should cost."""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent.config import Model, model

PLAN = Path(__file__).with_name("plan.toml")

ClaimSet = Literal["all", "tiny"]
# How many claims each set holds: the queue's 25, or its five tiny ones
SET_SIZES: dict[str, int] = {"all": 25, "tiny": 5}


@dataclass(frozen=True)
class Trial:
    """One model on a set of claims, with N claim agents at once, run a number
    of times."""

    model: Model
    claims: ClaimSet
    repeats: int
    agents: int


@dataclass(frozen=True)
class Estimate:
    """What a claim is expected to use, in tokens."""

    input_tokens: int
    output_tokens: int

    def cost(self, chosen: Model, claims: int) -> float:
        """What working this many claims on a model should cost, in US dollars."""
        return chosen.cost(self.input_tokens, self.output_tokens) * claims


def load(path: Path = PLAN) -> tuple[list[Trial], Estimate]:
    """Read the trials and the estimate from the plan."""
    with path.open("rb") as file:
        plan = tomllib.load(file)
    trials = [
        Trial(model(trial["model"]), trial["claims"], trial["repeats"], trial["agents"])
        for trial in plan["trials"]
    ]
    estimate = plan["estimate"]
    return trials, Estimate(
        estimate["input_tokens_per_claim"], estimate["output_tokens_per_claim"]
    )
