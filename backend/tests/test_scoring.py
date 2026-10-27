import pytest

from backend.scoring import (
    Answer,
    Scored,
    agents_answer,
    is_right,
    measures,
    mistake_cost,
)

APPROVE_420 = Answer("approve", 420.0)


@pytest.mark.parametrize(
    ("answer", "expected", "cost"),
    [
        (Answer("approve", 400.0), APPROVE_420, 20.0),
        (Answer("decline", 0), APPROVE_420, 1500),
        (Answer("approve", 2240.0), Answer("decline", 0), 2240.0),
        (Answer("approve", 300.0), Answer("refer", 0), 300.0),
        (Answer("refer", 0), APPROVE_420, 50),
        (Answer("refer", 0), Answer("decline", 0), 50),
        (Answer("decline", 0), Answer("decline", 0), 0),
        (Answer("refer", 0), Answer("refer", 0), 0),
    ],
)
def test_what_each_mistake_costs(answer, expected, cost):
    assert mistake_cost(answer, expected) == pytest.approx(cost)


def test_a_wrongful_approval_costs_its_payout_whether_or_not_it_was_paid():
    """The payout is the agent's decision; whether it was paid isn't asked."""
    held = Answer("approve", 2240.0)
    assert mistake_cost(held, Answer("decline", 0)) == 2240.0


def test_a_payout_within_a_dollar_is_right():
    assert is_right(Answer("approve", 420.99), APPROVE_420)
    assert not is_right(Answer("approve", 421.01), APPROVE_420)
    assert not is_right(Answer("decline", 0), APPROVE_420)


def test_a_claim_the_agent_didnt_decide_is_a_referral():
    assert agents_answer(None, None) == Answer("refer", 0)
    assert agents_answer("approve", 420.0) == APPROVE_420
    assert agents_answer("decline", None) == Answer("decline", 0)


def test_the_measures_of_a_hand_made_evaluation():
    claims = [
        Scored(APPROVE_420, APPROVE_420, 0.002, 10),
        Scored(Answer("approve", 300.0), APPROVE_420, 0.002, 20),
        Scored(Answer("refer", 0), Answer("decline", 0), 0.002, 30),
        Scored(Answer("decline", 0), Answer("approve", 100.0), 0.002, 40),
    ]
    assert measures(claims) == pytest.approx(
        {
            "decision_accuracy": 0.5,
            "accuracy": 0.25,
            "cost_of_mistakes": 120 + 50 + 1500,
            "straight_through": 0.75,
            "model_cost_per_claim": 0.002,
            "seconds_per_claim": 25,
        }
    )
