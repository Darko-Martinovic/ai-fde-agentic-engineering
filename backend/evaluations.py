"""Evaluations: the agent's work on copies of a labelled set's claims, scored
against the handlers' decisions. The dashboard starts one through the backend,
which asks the agent's service; the service records it under /api/runs, which
makes the copies; and the scoreboard reads them under /api/evaluations, scored
when they're read. Nothing the agent reads holds the handlers' decisions."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection, RowMapping

from backend import agent_service, scoring
from backend.api import Db, now
from backend.run_models import (
    EVALUATION,
    Evaluation,
    EvaluationClaim,
    EvaluationIn,
    Measures,
    Run,
    RunClaim,
    Started,
)
from backend.run_views import load_run
from backend.signed_in import signed_in
from backend.store import evaluations, runs, versions

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


@router.post("/runs/evaluations", operation_id="create_evaluation")
def create_evaluation(start: EvaluationIn, conn: Db) -> Run:
    """Record a new evaluation, running, on the current version, with its copies."""
    run = (
        start.model_dump()
        | versions.run_on(conn, versions.current(conn))
        | {"kind": EVALUATION, "started_at": now()}
    )
    run_id = runs.add(conn, run)
    runs.set_claims(conn, run_id, make_copies(conn, run_id, start))
    return load_run(conn, run_id)


def scored(
    claim: RunClaim, answered: RowMapping, key: dict[str, scoring.Answer]
) -> EvaluationClaim:
    """A copy beside the handler's decision on the claim it copies, scored on
    the agent's own decision."""
    answer = scoring.agents_answer(answered["decision"], answered["payout"])
    expected = key[answered["copy_of"]]
    return EvaluationClaim.model_validate(
        claim.model_dump()
        | {
            "decision": answered["decision"],
            "payout": answered["payout"],
            "copy_of": answered["copy_of"],
            "reasons": answered["reasons"],
            "handler_decision": expected.decision,
            "handler_payout": expected.payout,
            "right": scoring.is_right(answer, expected),
            "mistake_cost": scoring.mistake_cost(answer, expected),
        }
    )


def measured(copies: list[EvaluationClaim], run_seconds: float | None) -> Measures:
    """An evaluation's measures, from its scored copies."""
    return Measures(
        **scoring.measures(
            [
                scoring.Scored(
                    scoring.agents_answer(c.decision, c.payout),
                    scoring.Answer(c.handler_decision, c.handler_payout),
                    c.model_cost,
                    c.seconds,
                )
                for c in copies
            ]
        ),
        run_seconds=run_seconds,
    )


def load_evaluation(conn: Connection, run_id: int) -> Evaluation:
    """An evaluation with its copies beside the handlers' decisions, scored."""
    run = load_run(conn, run_id)
    if run.evaluation_set is None:
        raise HTTPException(404, f"Evaluation {run_id} not found")
    key = {
        claim_id: scoring.Answer(row["decision"], row["payout"])
        for claim_id, row in evaluations.handler_decisions(
            conn, run.evaluation_set
        ).items()
    }
    answers = evaluations.agents_answers(conn, run_id)
    copies = [scored(claim, answers[claim.claim_id], key) for claim in run.claims]
    return Evaluation.model_validate(
        run.model_dump(exclude={"claims"})
        | {"measures": measured(copies, run.seconds), "claims": copies}
    )


@router.get("/evaluations", operation_id="list_evaluations")
def list_evaluations(conn: Db) -> list[Evaluation]:
    """List every evaluation, newest first, with its measures."""
    return [load_evaluation(conn, run_id) for run_id in runs.of_kind(conn, EVALUATION)]


@router.get("/evaluations/{run_id}", operation_id="get_evaluation")
def get_evaluation(run_id: int, conn: Db) -> Evaluation:
    """Get one evaluation with its measures and its copies beside the handlers'."""
    return load_evaluation(conn, run_id)
