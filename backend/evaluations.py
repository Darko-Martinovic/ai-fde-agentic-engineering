"""Evaluations: the agent's work on copies of a labelled set's claims, scored
against the handlers' decisions. The dashboard starts one through the backend,
which asks the agent's service; the service records it under /api/runs, which
makes the copies; and the scoreboard reads them under /api/evaluations, scored
when they're read. Nothing the agent reads holds the handlers' decisions."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection

from backend import agent_service, spending
from backend.api import Db, now
from backend.callers import AGENT, HANDLER
from backend.evaluation_views import load_evaluation
from backend.round_models import RoundEvaluationIn
from backend.round_views import require_open
from backend.run_models import (
    EVALUATION,
    Evaluation,
    EvaluationIn,
    Run,
    Started,
)
from backend.run_views import load_run
from backend.signed_in import signed_in
from backend.store import evaluations, platform_settings, runs, versions
from backend.version_scores import NEEDED

router = APIRouter(prefix="/api")


def copy_id(claim_id: str, run_id: int) -> str:
    """A copy's id: the original's, with its evaluation's number."""
    return f"{claim_id}-E{run_id}"


def make_copies(conn: Connection, run_id: int, start: EvaluationIn) -> list[str]:
    """Copy the set's claims, or its tiny ones, into the evaluation, each with
    its new id in its record too; return the copies' ids, oldest first."""
    tiny = {
        claim_id
        for claim_id, decided in evaluations.handler_decisions(
            conn, start.evaluation_set
        ).items()
        if decided["tiny"]
    }
    originals = [
        record
        for record in evaluations.originals(conn, start.evaluation_set)
        if not start.tiny or record["claim_id"] in tiny
    ]
    copies = [
        {
            "record": record | {"claim_id": copy_id(record["claim_id"], run_id)},
            "copy_of": record["claim_id"],
        }
        for record in originals
    ]
    evaluations.add_copies(conn, run_id, copies)
    return [copy["record"]["claim_id"] for copy in copies]


@router.post(
    "/evaluations",
    operation_id="start_evaluation",
    status_code=202,
    dependencies=[Depends(signed_in)],
)
def start_evaluation(start: EvaluationIn) -> Started:
    """Ask the agent's service to start an evaluation with N claim agents at once."""
    asked = agent_service.start_evaluation(
        start.evaluation_set, start.tiny, start.agents
    )
    return Started.model_validate(asked)


def record_evaluation(
    conn: Connection, start: EvaluationIn, version: int, round_id: int | None
) -> Run:
    """Record a new evaluation, running, on a version, with its copies."""
    run = (
        start.model_dump()
        | versions.run_on(conn, version)
        | {"kind": EVALUATION, "started_at": now(), "round_id": round_id}
    )
    run_id = runs.add(conn, run)
    runs.set_claims(conn, run_id, make_copies(conn, run_id, start))
    return load_run(conn, run_id)


@router.post(
    "/runs/evaluations", operation_id="create_evaluation", dependencies=[AGENT]
)
def create_evaluation(start: EvaluationIn, conn: Db) -> Run:
    """Record a new evaluation, running, on the current version, with its copies."""
    return record_evaluation(conn, start, versions.current(conn), None)


def round_version(conn: Connection, row: dict[str, Any], evaluation_set: str) -> int:
    """The version a round evaluates next on a set: the one it started from, in
    its first evaluations, then the one it tried, until its verdict. The first
    evaluation of the version tried is refused when the round can't afford all
    three."""
    round_id, tried = row["round_id"], row["version_tried"]
    if tried is None:
        version, needed = row["version_before"], row["first_evaluations"]
        times = needed.count(evaluation_set)
    elif row["verdict"] is None:
        version, times = tried, NEEDED[evaluation_set]
    else:
        raise HTTPException(409, f"Round {round_id} has judged version {tried}")
    ran = [r for r in runs.of_round(conn, round_id) if r["version"] == version]
    if sum(r["evaluation_set"] == evaluation_set for r in ran) >= times:
        raise HTTPException(
            409,
            f"Round {round_id} has run its evaluations of version {version}"
            f" on the {evaluation_set} set",
        )
    if tried is not None and version == tried and not ran:
        refuse_unless_affordable(conn, row, tried)
    return version


def refuse_unless_affordable(
    conn: Connection, row: dict[str, Any], version: int
) -> None:
    """Refuse a version's evaluations that could cost more than what's left of
    the round's spending limit."""
    limit = platform_settings.row(conn, row["settings_number"])["spending_limit"]
    left = limit - spending.spent(conn, row["round_id"])
    cost = spending.evaluations_cost(conn, version)
    if cost > left:
        raise HTTPException(
            409,
            f"The evaluations could cost about ${cost:.2f},"
            f" and ${max(left, 0):.2f} of the round's limit is left",
        )


@router.post(
    "/runs/rounds/{round_id}/evaluations",
    operation_id="create_round_evaluation",
    dependencies=[AGENT],
)
def create_round_evaluation(round_id: int, start: RoundEvaluationIn, conn: Db) -> Run:
    """Record a round's next evaluation of a whole set, at its agents at once."""
    row = require_open(conn, round_id)
    version = round_version(conn, row, start.evaluation_set)
    agents = platform_settings.row(conn, row["settings_number"])["agents"]
    evaluation = EvaluationIn(
        evaluation_set=start.evaluation_set, tiny=False, agents=agents
    )
    return record_evaluation(conn, evaluation, version, round_id)


@router.get("/evaluations", operation_id="list_evaluations", dependencies=[HANDLER])
def list_evaluations(conn: Db) -> list[Evaluation]:
    """List every evaluation, newest first, with its measures."""
    return [load_evaluation(conn, run_id) for run_id in runs.of_kind(conn, EVALUATION)]


@router.get(
    "/evaluations/{run_id}", operation_id="get_evaluation", dependencies=[HANDLER]
)
def get_evaluation(run_id: int, conn: Db) -> Evaluation:
    """Get one evaluation with its measures and its copies beside the handlers'."""
    return load_evaluation(conn, run_id)
