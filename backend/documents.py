"""The documents the agent works from: its instructions and the policy wording."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from backend.api import Db, setting

router = APIRouter(prefix="/api")

INSTRUCTIONS = Path(__file__).parent / "instructions.md"


@router.get(
    "/policy-wording",
    operation_id="get_policy_wording",
    response_class=PlainTextResponse,
)
def get_policy_wording(conn: Db) -> str:
    """Get the policy wording as Markdown."""
    return setting(conn, "policy_wording")


@router.get(
    "/instructions",
    operation_id="get_instructions",
    response_class=PlainTextResponse,
)
def get_instructions() -> str:
    """Get the UnderCover Agent's instructions as Markdown."""
    return INSTRUCTIONS.read_text(encoding="utf-8")
