"""What a round has spent of its limit, and what its evaluations are likely to
cost. A round's spending is its improver's model calls, every model call in
its evaluations, the first ones included, and the judge's grading of them."""

from sqlalchemy import Connection

from backend.store import (
    evaluations,
    grades,
    platform_settings,
    rounds,
    runs,
    usage,
    versions,
)
from backend.version_scores import NEEDED


def spent(conn: Connection, round_id: int) -> float:
    """What a round has spent so far."""
    run_ids = [run["run_id"] for run in runs.of_round(conn, round_id)]
    return (
        rounds.improver_cost(conn, round_id)
        + usage.cost_of_runs(conn, run_ids)
        + grades.judge_cost(conn, run_ids)
    )


def per_claim(conn: Connection, model: str, current_model: str) -> float:
    """What a claim on a model is likely to cost at most: the highest cost per
    claim of any finished run on it, or for a model with no runs yet, the
    current model's scaled by the larger ratio of their prices."""
    seen = usage.highest_cost_per_claim(conn, model)
    if seen is not None:
        return seen
    current = usage.highest_cost_per_claim(conn, current_model) or 0.0
    new = platform_settings.model(conn, model)
    old = platform_settings.model(conn, current_model)
    if new is None or old is None or not old["input_price"] or not old["output_price"]:
        return current
    ratio = max(
        new["input_price"] / old["input_price"],
        new["output_price"] / old["output_price"],
    )
    return current * ratio


def evaluations_cost(conn: Connection, version: int) -> float:
    """What the evaluations a round runs of a version it tried are likely to
    cost at most: each set's claims, as many times as it's evaluated, at the
    most a claim on its model is likely to cost."""
    model = versions.run_on(conn, version)["model"]
    current = versions.run_on(conn, versions.current(conn))["model"]
    claims = sum(
        needed * len(evaluations.originals(conn, name))
        for name, needed in NEEDED.items()
    )
    return claims * per_claim(conn, model, current)
