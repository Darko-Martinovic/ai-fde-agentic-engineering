"""The free model a student without credit runs everything on: the model in
MODEL_NAME, as provider:model. With it set, it's the only model allowed, at no
reasoning effort of its own and a price of 0, and the judge isn't called. The
only reader of MODEL_NAME."""

from typing import Any

from backend.version_models import NO_EFFORT
from settings import optional_setting


def free_model() -> dict[str, Any] | None:
    """The free model as a model allowed, or None when MODEL_NAME isn't set."""
    spec = optional_setting("MODEL_NAME")
    if spec is None:
        return None
    provider, model = spec.split(":", 1)
    return {
        "model": model,
        "label": model,
        "provider": provider,
        "reasoning_efforts": [NO_EFFORT],
        "input_price": 0.0,
        "output_price": 0.0,
        "options": {},
    }
