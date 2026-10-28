"""Improving the claim agent, as the dashboard reads and does it under
/api/improvement: the rounds so far and the recipe's versions, and a senior
handler's start or stop of a round and review of a proposal. A start and a
review go to the agent's service, which records them under /api/rounds; the
backend checks first, so a refusal asks nothing of the service."""

from typing import Annotated

from fastapi import APIRouter

from backend import agent_service, diffs
from backend.api import Db, found, transaction
from backend.models import Handler
from backend.round_models import (
    Improvement,
    Recipe,
    RecipeDetails,
    RejectionIn,
    Reviewing,
    Round,
    RoundStarted,
    RoundStatus,
)
from backend.round_rules import end, refuse_while_open, waiting_proposal
from backend.round_views import load_round, require_open
from backend.signed_in import senior
from backend.store import rounds

router = APIRouter(prefix="/api/improvement")

Starter = Annotated[Handler, senior("start a round of improvement")]
Stopper = Annotated[Handler, senior("stop a round of improvement")]
Reviewer = Annotated[Handler, senior("review the improver's proposals")]


@router.get("", operation_id="get_improvement")
def get_improvement(conn: Db) -> Improvement:
    """Get every round, newest first, and every version of the recipe."""
    return Improvement(
        rounds=[load_round(conn, row["round_id"]) for row in rounds.every(conn)],
        recipes=[Recipe.model_validate(row) for row in rounds.every_recipe(conn)],
        current_recipe=rounds.current_recipe(conn),
    )


@router.get("/recipes/{number}", operation_id="get_recipe")
def get_recipe(number: int, conn: Db) -> RecipeDetails:
    """Get one version of the recipe with what it changed from the one before."""
    row = found(rounds.recipe(conn, number), "Recipe", str(number))
    before = rounds.recipe(conn, row["based_on"]) if row["based_on"] else None
    old = before["recipe"] if before else row["recipe"]
    return RecipeDetails.model_validate(
        dict(row) | {"changes": diffs.changes(old, row["recipe"])}
    )


@router.post("/rounds", operation_id="start_round", status_code=202)
def start_round(handler: Starter) -> RoundStarted:
    """Ask the agent's service to start a round of improvement."""
    with transaction() as conn:
        refuse_while_open(conn)
    return RoundStarted.model_validate(agent_service.start_round(handler.handler_id))


@router.post("/rounds/{round_id}/stop", operation_id="stop_round")
def stop_round(round_id: int, handler: Stopper) -> Round:
    """Stop an open round, rolling back a version it hasn't judged yet."""
    with transaction() as conn:
        row = require_open(conn, round_id)
        reason = f"Stopped by {handler.name}"
        end(conn, row, RoundStatus.STOPPED, reason, handler.handler_id)
        return load_round(conn, round_id)


def review(
    round_id: int, proposal_id: int, handler: Handler, approved: bool, note: str
) -> Reviewing:
    """Pass a review of the proposal waiting to the agent's service, which
    records it and carries the round on."""
    with transaction() as conn:
        require_open(conn, round_id)
        waiting_proposal(conn, round_id, proposal_id)
    agent_service.review_proposal(
        round_id, proposal_id, handler.handler_id, approved, note
    )
    return Reviewing(round_id=round_id, proposal_id=proposal_id)


@router.post(
    "/rounds/{round_id}/proposals/{proposal_id}/approval",
    operation_id="approve_proposal",
    status_code=202,
)
def approve_proposal(round_id: int, proposal_id: int, handler: Reviewer) -> Reviewing:
    """Approve the improver's proposal waiting in a round."""
    return review(round_id, proposal_id, handler, True, "")


@router.post(
    "/rounds/{round_id}/proposals/{proposal_id}/rejection",
    operation_id="reject_proposal",
    status_code=202,
)
def reject_proposal(
    round_id: int, proposal_id: int, rejection: RejectionIn, handler: Reviewer
) -> Reviewing:
    """Reject the improver's proposal waiting in a round, saying what's wrong."""
    return review(round_id, proposal_id, handler, False, rejection.note)
