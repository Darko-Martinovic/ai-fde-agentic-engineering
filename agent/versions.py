"""The claim agent's configuration, as a version of it gives it: its
instructions and its model, which the harness builds the claim agent from."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Model:
    """The model a version runs on: its name, as the models allowed list it, its
    provider, and the options it's built with, its reasoning effort among
    them."""

    name: str
    provider: str
    options: dict[str, Any]


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
            options=fetched["options"],
        ),
    )
