"""A round as the API shows it: its records, where it has got to, worked out
from them, what it has spent of its limit, and its proposal waiting for a
handler, if it has one."""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import Connection, RowMapping

from backend import diffs, spending
from backend.api import found
from backend.round_models import (
    Progress,
    Proposal,
    ProposalKind,
    ProposalView,
    Round,
    RoundStatus,
    Stage,
)
from backend.store import platform_settings, rounds, runs, versions

# The evaluations a version tried in a round gets: one of the evaluation set
# and two of the held-out set
EVALUATIONS_OF_A_CHANGE = 3
WAITING = {
    ProposalKind.CHANGE: Stage.CHANGE_WAITING,
    ProposalKind.RECIPE: Stage.RECIPE_WAITING,
}


def load(conn: Connection, round_id: int) -> dict[str, Any]:
    return found(rounds.round_(conn, round_id), "Round", str(round_id))


def require_open(conn: Connection, round_id: int) -> dict[str, Any]:
    """A round still open, or refuse whatever it would record."""
    row = load(conn, round_id)
    if row["status"] != RoundStatus.OPEN:
        raise HTTPException(409, f"Round {round_id} is {row['status']}")
    return row


def cut_short(conn: Connection, round_id: int) -> str | None:
    """Why a round's evaluations can't go on, if they can't: the round has
    ended, or it has spent its limit."""
    row = load(conn, round_id)
    if row["status"] != RoundStatus.OPEN:
        return f"Round {round_id} is {row['status']}"
    limit = platform_settings.row(conn, row["settings_number"])["spending_limit"]
    if spending.spent(conn, round_id) >= limit:
        return f"Round {round_id} has spent its limit of ${limit:.2f}"
    return None


def waiting(conn: Connection, round_id: int) -> Proposal | None:
    """The round's proposal waiting for a handler's review, if any."""
    pending = [p for p in rounds.round_proposals(conn, round_id) if p["review"] is None]
    return Proposal.model_validate(pending[-1]) if pending else None


def evaluations_on(
    evaluations: list[RowMapping], version: int | None
) -> list[RowMapping]:
    return [run for run in evaluations if run["version"] == version]


def stage(
    row: dict[str, Any], evaluations: list[RowMapping], pending: Proposal | None
) -> tuple[Stage, Progress | None]:
    """Where a round has got to, from its records, with how far a stage with
    steps has got: the evaluation underway, or the next. The verdict stands
    from the version's last evaluation until the improver proposes a recipe."""
    if row["status"] != RoundStatus.OPEN:
        return Stage(row["status"]), None
    if pending:
        return WAITING[pending.kind], None
    if row["verdict"] is not None:
        return Stage.VERDICT, None
    return evaluating(row, evaluations)


def evaluating(
    row: dict[str, Any], evaluations: list[RowMapping]
) -> tuple[Stage, Progress | None]:
    """Where an open round with nothing waiting and no verdict has got to: its
    first evaluations, the improver at work, then the evaluations of the
    version it tried, until its verdict."""
    tried = row["version_tried"]
    if tried is None:
        first = len(row["first_evaluations"])
        before = evaluations_on(evaluations, row["version_before"])
        if progress(before) < first:
            return Stage.FIRST_EVALUATIONS, Progress(step=step(before), of=first)
        return Stage.IMPROVING, None
    done = evaluations_on(evaluations, tried)
    if progress(done) < EVALUATIONS_OF_A_CHANGE:
        return Stage.EVALUATING, Progress(step=step(done), of=EVALUATIONS_OF_A_CHANGE)
    return Stage.VERDICT, None


def progress(evaluations: list[RowMapping]) -> int:
    """How many of some evaluations have ended."""
    return sum(run["status"] != "running" for run in evaluations)


def step(evaluations: list[RowMapping]) -> int:
    """The evaluation underway, counting from 1, or the next to start."""
    return progress(evaluations) + 1


def proposal_view(
    conn: Connection, row: dict[str, Any], proposal: dict[str, Any]
) -> ProposalView:
    """A proposal beside what it would change, against the version and the
    recipe the round started from."""
    proposed = proposal["proposed"]
    before: dict[str, Any] = {"model_before": None, "reasoning_effort_before": None}
    if proposal["kind"] == ProposalKind.CHANGE:
        version = found(versions.version(conn, row["version_before"]), "Version", "")
        old, new = version["instructions"], proposed["instructions"]
        before = {
            "model_before": version["model"],
            "reasoning_effort_before": version["reasoning_effort"],
        }
    else:
        recipe = found(rounds.recipe(conn, row["recipe_number"]), "Recipe", "")
        old, new = recipe["recipe"], proposed["recipe"]
    return ProposalView.model_validate(
        proposal | before | {"changes": diffs.changes(old, new)}
    )


def load_round(conn: Connection, round_id: int) -> Round:
    """A round as it stands."""
    row = load(conn, round_id)
    evaluations = runs.of_round(conn, round_id)
    pending = waiting(conn, round_id)
    where, how_far = stage(row, evaluations, pending)
    settings = platform_settings.row(conn, row["settings_number"])
    proposed = rounds.round_proposals(conn, round_id)
    return Round.model_validate(
        row
        | {
            "stage": where,
            "progress": how_far,
            "spent": spending.spent(conn, round_id),
            "spending_limit": settings["spending_limit"],
            "proposals": proposed,
            "waiting": next(
                (
                    proposal_view(conn, row, p)
                    for p in proposed
                    if pending and p["proposal_id"] == pending.proposal_id
                ),
                None,
            ),
        }
    )
