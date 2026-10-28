"""Grading an evaluation's claims with the judge as it finishes: what each
graded claim needs, read on one connection, and the judge's grades, asked for
in parallel, one thread for each claim, with no database connection held while
the judge answers. A claim the agent didn't decide is an F without a call."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Connection

from backend import judge
from backend.store import evaluations


@dataclass(frozen=True)
class Case:
    """One copy to grade: the handler's decision, reason and reference on the
    claim it copies, and the agent's decision, reason and section, or none."""

    claim_id: str
    handler: dict[str, Any]
    agent: dict[str, Any] | None = field(default=None)


def cases(conn: Connection, run_id: int, evaluation_set: str) -> list[Case]:
    """Every copy in an evaluation, beside the handler's decision on it."""
    key = evaluations.handler_decisions(conn, evaluation_set)
    answers = evaluations.agents_answers(conn, run_id)
    return [
        Case(
            claim_id=copy_id,
            handler={
                "decision": key[answer["copy_of"]]["decision"],
                "reason": key[answer["copy_of"]]["reason"],
                "reference": key[answer["copy_of"]]["reference"],
            },
            agent=(
                {
                    "decision": answer["decision"],
                    "reason": answer["reasons"],
                    "section": answer["policy_section"],
                }
                if answer["decision"]
                else None
            ),
        )
        for copy_id, answer in answers.items()
    ]


def graded(case: Case) -> judge.Grade | None:
    """A copy's grade: an F for one the agent didn't decide, or the judge's."""
    if case.agent is None:
        return judge.UNDECIDED
    return judge.grade(case.handler, case.agent)


def grade_all(to_grade: list[Case]) -> dict[str, judge.Grade]:
    """Each copy's grade, by its id, leaving out those the judge couldn't grade."""
    if not to_grade:
        return {}
    with ThreadPoolExecutor(max_workers=len(to_grade)) as pool:
        grades = list(pool.map(graded, to_grade))
    return {
        case.claim_id: grade
        for case, grade in zip(to_grade, grades, strict=True)
        if grade is not None
    }
