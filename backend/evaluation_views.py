"""An evaluation as the API shows it: its copies, each scored beside the
handler's decision on the claim it copies, with the judge's grade, and its
measures, worked out when it's read with the lab's (scoring.py)."""

from fastapi import HTTPException
from sqlalchemy import Connection, RowMapping

from backend import scoring
from backend.run_models import Evaluation, EvaluationClaim, Measures, RunClaim
from backend.run_views import load_run
from backend.store import evaluations, grades


def graded(row: RowMapping | None) -> dict[str, object]:
    """A copy's grade as the API shows it, or no grade."""
    if row is None:
        return {
            "grade": None,
            "letter": None,
            "same_grounds": None,
            "same_section": None,
            "judge_cost": 0.0,
        }
    return {
        "grade": row["score"],
        "letter": row["letter"],
        "same_grounds": row["same_grounds"],
        "same_section": row["same_section"],
        "judge_cost": row["cost"],
    }


def scored(
    claim: RunClaim,
    answered: RowMapping,
    key: dict[str, scoring.Answer],
    grade: RowMapping | None,
) -> EvaluationClaim:
    """A copy beside the handler's decision on the claim it copies, scored on
    the agent's own decision, with the judge's grade, if it has one."""
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
        | graded(grade)
    )


def mean_grade(copies: list[EvaluationClaim]) -> float | None:
    """The judge's average grade over the copies it graded, or none."""
    scores = [c.grade for c in copies if c.grade is not None]
    return sum(scores) / len(scores) if scores else None


def measured(copies: list[EvaluationClaim], run_seconds: float | None) -> Measures:
    """An evaluation's measures, from its scored copies: the lab's, and the
    judge's grade and cost, apart from the claim agents'."""
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
        grade=mean_grade(copies),
        judge_cost=sum(c.judge_cost for c in copies),
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
    grade = grades.of_run(conn, run_id)
    copies = [
        scored(claim, answers[claim.claim_id], key, grade.get(claim.claim_id))
        for claim in run.claims
    ]
    return Evaluation.model_validate(
        run.model_dump(exclude={"claims"})
        | {"measures": measured(copies, run.seconds), "claims": copies}
    )
