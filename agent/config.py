"""The models the agent may run on, from models.toml. Its other settings are the
shared ones in settings.py."""

import tomllib
from dataclasses import dataclass
from functools import cache
from typing import Any

from settings import ROOT, setting


@dataclass(frozen=True)
class Model:
    """A model the agent may run on, as listed in models.toml."""

    spec: str
    label: str
    input_price: float
    output_price: float
    options: dict[str, Any]

    @property
    def provider(self) -> str:
        return self.spec.split(":", 1)[0]

    @property
    def name(self) -> str:
        return self.spec.split(":", 1)[1]


@cache
def models() -> dict[str, Model]:
    """Return the models allowed, by their spec."""
    with (ROOT / "models.toml").open("rb") as file:
        return {m["spec"]: Model(**m) for m in tomllib.load(file)["models"]}


def model(spec: str) -> Model:
    """Return an allowed model, or say that the spec isn't one."""
    if spec not in models():
        raise ValueError(f"{spec} is not one of the models in models.toml")
    return models()[spec]


def current_model() -> Model:
    """Return the model in MODEL_NAME."""
    return model(setting("MODEL_NAME"))
