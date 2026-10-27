"""Scoring an evaluation with the measures from labs/week2day4.ipynb: how often
the agent's decision matches the handler's, how often its payout does too, what
its mistakes cost UnderCover, how many claims go straight through, and what a
claim costs and takes. A claim the agent didn't decide counts as a referral."""

from dataclasses import dataclass

# What a mistake costs UnderCover, beside a wrongful approval's payout
WRONGFUL_DECLINE = 1500
NEEDLESS_REFERRAL = 50
# A payout within a dollar of the handler's is right
PAYOUT_TOLERANCE = 1
REFER = "refer"


@dataclass(frozen=True)
class Answer:
    """A decision and its payout: the agent's, or the handler's."""

    decision: str
    payout: float


def agents_answer(decision: str | None, payout: float | None) -> Answer:
    """The agent's answer on a claim, a referral when it decided nothing."""
    if decision is None:
        return Answer(REFER, 0)
    return Answer(decision, payout or 0)


def is_right(answer: Answer, expected: Answer) -> bool:
    """The decision matches the handler's, and the payout is within a dollar."""
    close = abs(answer.payout - expected.payout) <= PAYOUT_TOLERANCE
    return answer.decision == expected.decision and close


def mistake_cost(answer: Answer, expected: Answer) -> float:
    """What the agent's answer costs UnderCover, against the handler's: the
    difference on a right approval, $1,500 for a wrongful decline, the payout
    for a wrongful approval whether or not it was paid, and $50 for a needless
    referral."""
    if answer.decision == expected.decision:
        if answer.decision == "approve":
            return abs(answer.payout - expected.payout)
        return 0
    if answer.decision == "decline":
        return WRONGFUL_DECLINE
    if answer.decision == "approve":
        return answer.payout
    return NEEDLESS_REFERRAL


@dataclass(frozen=True)
class Scored:
    """One claim of an evaluation: the agent's answer, the handler's, and what
    the claim cost and took."""

    answer: Answer
    expected: Answer
    model_cost: float
    seconds: float


def measures(claims: list[Scored]) -> dict[str, float]:
    """An evaluation's measures, from its claims."""
    count = len(claims) or 1
    return {
        "decision_accuracy": sum(
            c.answer.decision == c.expected.decision for c in claims
        )
        / count,
        "accuracy": sum(is_right(c.answer, c.expected) for c in claims) / count,
        "cost_of_mistakes": sum(mistake_cost(c.answer, c.expected) for c in claims),
        "straight_through": sum(c.answer.decision != REFER for c in claims) / count,
        "model_cost_per_claim": sum(c.model_cost for c in claims) / count,
        "seconds_per_claim": sum(c.seconds for c in claims) / count,
    }
