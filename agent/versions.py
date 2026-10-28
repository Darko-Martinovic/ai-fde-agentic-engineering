"""The claim agent's configuration, as a version of it gives it: its
instructions and its model, which the harness builds the claim agent from."""

from dataclasses import dataclass
from typing import Any

# A model run with no reasoning effort of its own, as a free model is
NO_EFFORT = "default"
# The retries of a model call that fails at the provider, the first after this
# many seconds, for every agent
MODEL_RETRIES = 2
RETRY_DELAY = 1.0


@dataclass(frozen=True)
class Model:
    """The model a version runs on: its name, as the models allowed list it, its
    provider, its reasoning effort and the options it's built with."""

    name: str
    provider: str
    reasoning_effort: str
    options: dict[str, Any]

    @property
    def build_options(self) -> dict[str, Any]:
        """The options to build it with, with its reasoning effort unless it
        runs with none of its own."""
        if self.reasoning_effort == NO_EFFORT:
            return self.options
        return self.options | {"reasoning_effort": self.reasoning_effort}


@dataclass(frozen=True)
class Version:
    number: int
    instructions: str
    model: Model


def version(fetched: dict[str, Any]) -> Version:
    """A version as the backend's `get_version` gives it."""
    return Version(
        number=fetched["number"],
        instructions=fetched["instructions"],
        model=Model(
            name=fetched["model"],
            provider=fetched["provider"],
            reasoning_effort=fetched["reasoning_effort"],
            options=fetched["options"],
        ),
    )
