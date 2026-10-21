"""Scoring the agent's decisions against the handlers' own, in data/evals/."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bench.plan import ClaimSet
from settings import ROOT

ANSWER_KEY = ROOT / "data" / "evals" / "decisions.json"
# A payout this close to the handlers' counts as the same, in US dollars
PAYOUT_TOLERANCE = 1.0


@dataclass(frozen=True)
class Answer:
    """The handlers' decision on a claim, and its payout."""

    claim_id: str
    decision: str
    payout: float
    tiny: bool


@dataclass(frozen=True)
class Outcome:
    """What the agent left on a claim: its last decision and payout, if any,
    and the claim's state."""

    claim_id: str
    decision: str | None
    payout: float | None
    status: str


def answers(path: Path = ANSWER_KEY) -> dict[str, Answer]:
    """Read the handlers' decisions, by claim."""
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {
        row["claim_id"]: Answer(
            row["claim_id"], row["decision"], float(row["payout"]), bool(row["tiny"])
        )
        for row in rows
    }


def chosen(key: dict[str, Answer], claims: ClaimSet) -> list[str]:
    """The claims of a set: all of them, or the five tiny ones."""
    return sorted(a.claim_id for a in key.values() if claims == "all" or a.tiny)


def outcome(claim: dict[str, Any]) -> Outcome:
    """Read what the agent left on a claim from the claim as the API gives it."""
    last = claim["decisions"][-1] if claim["decisions"] else None
    if last is None:
        return Outcome(claim["claim_id"], None, None, claim["status"])
    return Outcome(
        claim["claim_id"], last["decision"], float(last["payout"]), claim["status"]
    )


def decision_right(answer: Answer, got: Outcome) -> bool:
    return got.decision == answer.decision


def payout_right(answer: Answer, got: Outcome) -> bool:
    """The decision is right and, for an approval, so is the payout."""
    if not decision_right(answer, got):
        return False
    if answer.decision != "approve":
        return True
    return abs((got.payout or 0.0) - answer.payout) <= PAYOUT_TOLERANCE
