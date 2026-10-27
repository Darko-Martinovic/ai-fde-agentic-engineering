"""The models the agent may run on, from settings/models.toml, for the
dashboard's choice of model."""

from fastapi import APIRouter
from pydantic import BaseModel

from agent.config import current_model, models

router = APIRouter(prefix="/api")


class ModelChoice(BaseModel):
    spec: str
    label: str
    default: bool


@router.get("/models", operation_id="list_models")
def list_models() -> list[ModelChoice]:
    """List the models the agent may run on, marking the default (MODEL_NAME)."""
    default = current_model().spec
    return [
        ModelChoice(spec=m.spec, label=m.label, default=m.spec == default)
        for m in models().values()
    ]
