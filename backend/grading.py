"""Grading an evaluation's claims with the judge as it finishes: what each
graded claim needs, read on one connection, and the judge's grades, asked for
in parallel, one thread for each claim, with no database connection held while
the judge answers. A claim the agent didn't decide is an F without a call."""

from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Connection

from backend import judge
from backend.free_model import free_model
from backend.run_models import Grade, Run
from backend.store import evaluations

# A copy the agent didn't decide
UNDECIDED = Grade(
    grade=0.0, letter=judge.GRADES[0], same_grounds=0, same_section=0, judge_cost=0
)
# However each call's connection, writing and reading go, the whole grading
# waits no longer than this, well within the agent's 30 seconds for the
# backend; a copy still waiting is ungraded
GRADING_SECONDS = 15


@dataclass(frozen=True)
class Case:
    """One copy to grade: the handler's decision, reason and reference on the
    claim it copies, and the agent's decision, reason and section, or none."""

    claim_id: str
    handler: dict[str, Any]
    agent: dict[str, Any] | None = None


def cases(conn: Connection, run: Run, stopped: bool) -> list[Case]:
    """What a finishing run has to grade: every copy of an evaluation beside
    the handler's decision on it; nothing for a dispatch, an evaluation that
    stopped, or a free model, which has no judge."""
    if stopped or run.evaluation_set is None or free_model():
        return []
    key = evaluations.handlers_reasons(conn, run.evaluation_set)
    answers = evaluations.agents_answers(conn, run.run_id)
    return [
        Case(
            claim_id=copy_id,
            handler=key[answer["copy_of"]],
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


def grade_all(to_grade: list[Case]) -> dict[str, Grade]:
    """Each copy's grade, by its id: an F for an undecided one, the judge's for
    the rest, leaving out those it couldn't grade in time."""
    graded = {case.claim_id: UNDECIDED for case in to_grade if case.agent is None}
    asking = [
        (case.claim_id, case.handler, case.agent)
        for case in to_grade
        if case.agent is not None
    ]
    if not asking:
        return graded
    judge.client()  # made once, before the threads share it
    pool = ThreadPoolExecutor(max_workers=len(asking))
    futures = {
        pool.submit(judge.grade, handler, agent): claim_id
        for claim_id, handler, agent in asking
    }
    done, _ = wait(futures, timeout=GRADING_SECONDS)
    pool.shutdown(wait=False, cancel_futures=True)
    for future in done:
        if (grade := future.result()) is not None:
            graded[futures[future]] = grade
    return graded
