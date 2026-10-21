import json

from bench.plan import load
from bench.score import (
    Answer,
    Outcome,
    answers,
    chosen,
    decision_right,
    outcome,
    payout_right,
)

APPROVE = Answer("CLM-1001", "approve", 420.0, True)
DECLINE = Answer("CLM-1005", "decline", 0.0, False)


def got(decision, payout, status="decided"):
    return Outcome("CLM-1001", decision, payout, status)


def test_an_approval_is_right_with_the_payout_within_a_dollar():
    assert payout_right(APPROVE, got("approve", 420.99))
    assert decision_right(APPROVE, got("approve", 380.0))
    assert not payout_right(APPROVE, got("approve", 380.0))
    assert not payout_right(APPROVE, got("approve", 421.5))


def test_a_decline_or_referral_needs_only_the_decision():
    assert payout_right(DECLINE, got("decline", 0.0))
    assert not decision_right(DECLINE, got("refer", 0.0))
    assert not payout_right(DECLINE, got("approve", 0.0))


def test_a_claim_left_undecided_is_wrong():
    undecided = got(None, None, "left_for_handler")
    assert not decision_right(APPROVE, undecided)
    assert not payout_right(APPROVE, undecided)


def test_the_outcome_is_the_last_decision():
    claim = {
        "claim_id": "CLM-1001",
        "status": "decided",
        "decisions": [
            {"decision": "refer", "payout": 0},
            {"decision": "approve", "payout": 420},
        ],
    }
    assert outcome(claim) == Outcome("CLM-1001", "approve", 420.0, "decided")
    claim["decisions"] = []
    assert outcome(claim) == Outcome("CLM-1001", None, None, "decided")


def test_answers_and_the_tiny_set(tmp_path, key):
    rows = [
        {
            "claim_id": a.claim_id,
            "decision": a.decision,
            "payout": a.payout,
            "tiny": a.tiny,
        }
        for a in key.values()
    ]
    path = tmp_path / "decisions.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    assert answers(path) == key
    assert chosen(key, "tiny") == ["CLM-1001", "CLM-1005"]
    assert chosen(key, "all") == ["CLM-1001", "CLM-1002", "CLM-1005"]


def test_the_plan_names_only_models_allowed():
    trials, estimate = load()
    assert trials
    assert all(
        trial.claims in {"all", "tiny"} and trial.repeats >= 1 for trial in trials
    )
    assert estimate.cost(trials[0].model, 0) == 0
