import pytest

from backend.round_models import Scores
from backend.verdict import keep_or_roll_back

SETTINGS = {
    "objectives": {"accuracy": 0.6, "grade": 1.0},
    "noise": {
        "accuracy": 0.1,
        "grade": 0.15,
        "cost_per_claim": 0.15,
        "seconds_per_claim": 0.15,
    },
    "tolerance": {
        "accuracy": 0.1,
        "grade": 0.15,
        "cost_per_claim": 1.0,
        "seconds_per_claim": 0.25,
    },
}
OLD = Scores(accuracy=0.60, grade=1.50, cost_per_claim=0.0010, seconds_per_claim=20)


def scores(**changes):
    return OLD.model_copy(update=changes)


@pytest.mark.parametrize(
    ("new", "kept", "why"),
    [
        (
            scores(accuracy=0.72, cost_per_claim=0.0019, seconds_per_claim=24),
            True,
            "accuracy improved",
        ),
        (
            scores(accuracy=0.72, cost_per_claim=0.0021, seconds_per_claim=24),
            False,
            "cost_per_claim got worse",
        ),
        (scores(cost_per_claim=0.0008), True, "cost_per_claim improved"),
        (
            scores(accuracy=0.68, grade=1.60),
            False,
            "no score improved by more than the noise",
        ),
        (scores(grade=0.90), False, "it missed the objectives on grade"),
        (scores(grade=None), False, "it has no grade"),
    ],
    ids=[
        "accuracy up, cost and time within tolerance",
        "cost past its tolerance",
        "cheaper",
        "inside the noise",
        "under the grade's floor",
        "no grade",
    ],
)
def test_the_rule_keeps_or_rolls_back_as_worked_out_by_hand(new, kept, why):
    assert keep_or_roll_back(new, OLD, SETTINGS) == (kept, why)
