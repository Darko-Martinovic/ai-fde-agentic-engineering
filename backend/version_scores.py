"""A version's scores: on each set, the averages of the finished evaluations of
the whole set that rounds ran on it. A Scoreboard evaluation, one of the five
tiny claims and one that stopped don't count. What the configuration's pages,
the rounds and the verdict all read."""

from statistics import mean

from sqlalchemy import Connection

from backend.evaluation_views import load_evaluation
from backend.round_models import Scores
from backend.store import runs

# What a version needs before a round can judge a change against it: one
# evaluation of the evaluation set and two of the held-out set
NEEDED = {"evaluation": 1, "held_out": 2}


def run_scores(conn: Connection, run_id: int) -> Scores:
    """One evaluation's scores, from its measures."""
    measures = load_evaluation(conn, run_id).measures
    return Scores(
        accuracy=measures.accuracy,
        grade=measures.grade,
        cost_per_claim=measures.model_cost_per_claim,
        seconds_per_claim=measures.seconds_per_claim,
    )


def averaged(scored: list[Scores]) -> Scores | None:
    """The average of some runs' scores, the grade over those with one, or
    none without any run."""
    if not scored:
        return None
    grades = [s.grade for s in scored if s.grade is not None]
    return Scores(
        accuracy=mean(s.accuracy for s in scored),
        grade=mean(grades) if grades else None,
        cost_per_claim=mean(s.cost_per_claim for s in scored),
        seconds_per_claim=mean(s.seconds_per_claim for s in scored),
    )


def version_scores(
    conn: Connection, version: int, round_id: int | None = None
) -> dict[str, Scores | None]:
    """A version's scores on each set, or only from one round's evaluations."""
    evaluated = [
        run
        for run in runs.scored_on(conn, version)
        if round_id is None or run["round_id"] == round_id
    ]
    return {
        name: averaged(
            [
                run_scores(conn, r["run_id"])
                for r in evaluated
                if r["evaluation_set"] == name
            ]
        )
        for name in NEEDED
    }


def evaluations_needed(conn: Connection, version: int) -> list[str]:
    """The evaluations a version still needs to be judged against, in order."""
    done = [run["evaluation_set"] for run in runs.scored_on(conn, version)]
    return [
        name
        for name, needed in NEEDED.items()
        for _ in range(max(0, needed - done.count(name)))
    ]
