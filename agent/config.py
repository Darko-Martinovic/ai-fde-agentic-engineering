"""The agent's settings: the environment, filled in from .env and then
.env.defaults, and the models it may run on, from models.toml."""

import os
import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

# The environment wins over .env, which wins over .env.defaults. Tests name
# .env.defaults alone in UNDERCOVER_ENV_FILES, so they never read .env.
for env_file in os.environ.get("UNDERCOVER_ENV_FILES", ".env,.env.defaults").split(","):
    load_dotenv(ROOT / env_file)


def setting(name: str) -> str:
    """Return one setting, which must be in the environment or an env file."""
    return os.environ[name]


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
