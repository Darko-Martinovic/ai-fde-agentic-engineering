"""Rounds of improvement, as only the agent's service records them under
/api/rounds: a round's start, what the improver reads and proposes, a
handler's review of each proposal, the version or recipe an approval makes,
the verdict on the version tried, the improver's model calls and the round's
end. The backend keeps the rules (round_rules.py), whoever asks. The
dashboard starts, stops and reviews rounds under /api/improvement."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from sqlalchemy import Connection

from backend.api import Db, found, now
from backend.free_model import free_model
from backend.improver_models import ImproverView
from backend.improver_view import improver_view
from backend.round_models import (
    ChangeIn,
    FinishRoundIn,
    ImproverCall,
    ImproverCallIn,
    ImproverModel,
    Proposal,
    ProposalKind,
    Recipe,
    RecipeIn,
    ReviewIn,
    Round,
    RoundIn,
    RoundStatus,
    RoundWork,
    Stopped,
    Verdict,
)
from backend.round_rules import (
    approved,
    decide,
    end,
    refuse_unless_allowed,
    refuse_while_open,
    refuse_while_waiting,
    senior_handler,
    verdict_of,
    waiting_proposal,
)
from backend.round_views import load, load_round, require_open, waiting
from backend.store import platform_settings, rounds, versions
from backend.version_models import ModelAllowed
from backend.version_scores import evaluations_needed
from settings import setting

router = APIRouter(prefix="/api/rounds")

IMPROVER = Path(__file__).parent / "instructions" / "improver.md"
RESTARTED = "The agent's service restarted while the round was working"


def improver_name() -> str:
    """The model a new round's improver runs on: the free model, or
    IMPROVER_MODEL."""
    free = free_model()
    return free["model"] if free else setting("IMPROVER_MODEL")


def improver_model(conn: Connection, name: str) -> ImproverModel:
    """How to build the improver's model, as a round recorded it: the free
    model at no effort of its own, or one of the models allowed at
    IMPROVER_REASONING_EFFORT."""
    free = free_model()
    if free and free["model"] == name:
        return ImproverModel(model=name, provider=free["provider"], options={})
    model = platform_settings.model(conn, name)
    if model is None:
        raise HTTPException(409, f"The improver's model, {name}, isn't one allowed")
    effort = {"reasoning_effort": setting("IMPROVER_REASONING_EFFORT")}
    return ImproverModel(
        model=name, provider=model["provider"], options=model["options"] | effort
    )


def instructions(conn: Connection, recipe_number: int) -> str:
    """The improver's instructions, with the recipe a round follows."""
    recipe = found(rounds.recipe(conn, recipe_number), "Recipe", str(recipe_number))
    goals = IMPROVER.read_text(encoding="utf-8")
    return f"{goals}\n\n# Your recipe\n\n{recipe['recipe']}"


def round_work(conn: Connection, round_id: int) -> RoundWork:
    """A round as the improver works it."""
    loaded = load_round(conn, round_id)
    return RoundWork.model_validate(
        loaded.model_dump()
        | {
            "instructions": instructions(conn, loaded.recipe_number),
            "improver": improver_model(conn, loaded.improver_model),
            "models_allowed": [
                ModelAllowed(**m) for m in platform_settings.models(conn)
            ],
        }
    )


def proposal(conn: Connection, round_id: int, proposal_id: int) -> Proposal:
    proposed = rounds.round_proposals(conn, round_id)
    return Proposal.model_validate(
        next(p for p in proposed if p["proposal_id"] == proposal_id)
    )


@router.post("", operation_id="create_round")
def create_round(start: RoundIn, conn: Db) -> RoundWork:
    """Record a new round, open, on the current settings, recipe and version."""
    refuse_while_open(conn)
    senior_handler(conn, start.handler_id, "start a round of improvement")
    current = versions.current(conn)
    round_id = rounds.add(
        conn,
        {
            "started_by": start.handler_id,
            "started_at": now(),
            "settings_number": platform_settings.current(conn)["number"],
            "recipe_number": rounds.current_recipe(conn),
            "version_before": current,
            "improver_model": improver_model(conn, improver_name()).model,
            "thread_id": start.thread_id,
            "first_evaluations": evaluations_needed(conn, current),
        },
    )
    return round_work(conn, round_id)


@router.post("/stop-all", operation_id="stop_rounds")
def stop_rounds(conn: Db) -> Stopped:
    """Stop every open round not waiting for a handler, as when the service starts."""
    stopped = []
    for round_id in rounds.open_ones(conn):
        if waiting(conn, round_id) is None:
            end(conn, load(conn, round_id), RoundStatus.STOPPED, RESTARTED)
            stopped.append(round_id)
    return Stopped(round_ids=stopped)


@router.get("/{round_id}", operation_id="get_round")
def get_round(round_id: int, conn: Db) -> RoundWork:
    """Get a round as the improver works it, with its instructions and recipe."""
    return round_work(conn, round_id)


@router.get("/{round_id}/view", operation_id="get_improver_view")
def get_improver_view(round_id: int, conn: Db) -> ImproverView:
    """Get what the improver reads: results, earlier rounds, objectives and limits."""
    return improver_view(conn, load(conn, round_id))


@router.post("/{round_id}/proposals/changes", operation_id="record_change_proposal")
def record_change_proposal(round_id: int, change: ChangeIn, conn: Db) -> Proposal:
    """Record a change the improver proposed, waiting for a handler's review."""
    row = require_open(conn, round_id)
    refuse_unless_allowed(conn, change.model, change.reasoning_effort)
    refuse_while_waiting(conn, round_id)
    if row["version_tried"] is not None:
        raise HTTPException(
            409, f"Round {round_id} has tried version {row['version_tried']} already"
        )
    return add_proposal(conn, round_id, ProposalKind.CHANGE, change)


@router.post("/{round_id}/proposals/recipes", operation_id="record_recipe_proposal")
def record_recipe_proposal(round_id: int, recipe: RecipeIn, conn: Db) -> Proposal:
    """Record a recipe the improver proposed, waiting for a handler's review."""
    require_open(conn, round_id)
    refuse_while_waiting(conn, round_id)
    made = rounds.recipe_of_round(conn, round_id)
    if made is not None:
        raise HTTPException(409, f"Round {round_id} has made recipe {made} already")
    return add_proposal(conn, round_id, ProposalKind.RECIPE, recipe)


def add_proposal(
    conn: Connection, round_id: int, kind: ProposalKind, proposed: ChangeIn | RecipeIn
) -> Proposal:
    proposal_id = rounds.add_proposal(
        conn,
        {
            "round_id": round_id,
            "kind": kind,
            "proposed": proposed.model_dump(exclude={"reason"}),
            "reason": proposed.reason,
            "proposed_at": now(),
        },
    )
    return proposal(conn, round_id, proposal_id)


@router.post("/{round_id}/proposals/{proposal_id}/review", operation_id="record_review")
def record_review(
    round_id: int, proposal_id: int, review: ReviewIn, conn: Db
) -> Proposal:
    """Record a handler's approval or rejection of the proposal waiting."""
    require_open(conn, round_id)
    handler = senior_handler(conn, review.handler_id)
    waiting_proposal(conn, round_id, proposal_id)
    reviewed = {
        "review": "approved" if review.approved else "rejected",
        "reviewed_by": handler.handler_id,
        "reviewed_at": now(),
        "review_note": review.note or None,
    }
    if not rounds.review(conn, proposal_id, reviewed):
        raise HTTPException(409, f"Proposal {proposal_id} has just been reviewed")
    return proposal(conn, round_id, proposal_id)


@router.post("/{round_id}/versions", operation_id="create_version")
def create_version(round_id: int, conn: Db) -> Round:
    """Make the approved change the version under test; a repeat returns it."""
    row = require_open(conn, round_id)
    if row["version_tried"] is None:
        change = approved(conn, round_id, ProposalKind.CHANGE)
        proposed = change["proposed"]
        refuse_unless_allowed(conn, proposed["model"], proposed["reasoning_effort"])
        number = versions.add(
            conn,
            proposed
            | {
                "based_on": row["version_before"],
                "reason": change["reason"],
                "proposed_by": f"Round {round_id}",
                "round_id": round_id,
                "approved_by": change["reviewed_by"],
                "approved_at": change["reviewed_at"],
                "created_at": now(),
            },
        )
        # Two requests at once make one version: the other's is undone
        if not rounds.try_version(conn, round_id, number):
            raise HTTPException(409, f"Round {round_id} has just made its version")
    return load_round(conn, round_id)


@router.post("/{round_id}/recipes", operation_id="create_recipe")
def create_recipe(round_id: int, conn: Db) -> Recipe:
    """Make the approved recipe the current one; a repeat returns it."""
    row = require_open(conn, round_id)
    made = rounds.recipe_of_round(conn, round_id)
    if made is None:
        recipe = approved(conn, round_id, ProposalKind.RECIPE)
        made = rounds.add_recipe(
            conn,
            {
                "recipe": recipe["proposed"]["recipe"],
                "based_on": row["recipe_number"],
                "reason": recipe["reason"],
                "proposed_by": f"Round {round_id}",
                "round_id": round_id,
                "approved_by": recipe["reviewed_by"],
                "approved_at": recipe["reviewed_at"],
                "created_at": now(),
            },
        )
    return Recipe.model_validate(rounds.recipe(conn, made))


@router.post("/{round_id}/verdict", operation_id="record_verdict")
def record_verdict(round_id: int, conn: Db) -> Verdict:
    """Keep or roll back the version tried by the rule; a repeat returns the verdict."""
    row = require_open(conn, round_id)
    if row["version_tried"] is None:
        raise HTTPException(409, f"Round {round_id} has no version to judge")
    if row["verdict"] is None:
        decide(conn, row)
    return verdict_of(conn, load(conn, round_id))


@router.post("/{round_id}/improver-calls", operation_id="record_improver_call")
def record_improver_call(round_id: int, call: ImproverCallIn, conn: Db) -> ImproverCall:
    """Record one of the improver's model calls, made even if the round has ended."""
    load(conn, round_id)
    row = call.model_dump() | {"recorded_at": now()}
    rounds.add_improver_call(conn, round_id, row)
    return ImproverCall.model_validate(row | {"round_id": round_id})


@router.post("/{round_id}/finish", operation_id="finish_round")
def finish_round(round_id: int, finish: FinishRoundIn, conn: Db) -> Round:
    """End an open round, finished or stopped, rolling back a version never judged."""
    row = require_open(conn, round_id)
    status = RoundStatus.STOPPED if finish.stopped else RoundStatus.FINISHED
    end(conn, row, status, finish.reason or None)
    return load_round(conn, round_id)
