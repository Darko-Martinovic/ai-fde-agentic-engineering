"""Running a trial once: a fresh database, the claims worked through the harness
in a run of their own, and what came of them, read through the API."""

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agent import api
from agent.__main__ import work_claims
from backend.seed import reset
from bench.plan import Trial
from bench.score import (
    Answer,
    Outcome,
    chosen,
    decision_right,
    outcome,
    payout_right,
)

RESULTS = Path(__file__).with_name("results.json")


@dataclass(frozen=True)
class Repeat:
    """One run of a trial: how many claims it got right, and what it used."""

    model: str
    label: str
    claims: str
    repeat: int
    worked: int
    decisions_right: int
    payouts_right: int
    undecided: int
    model_calls: int
    input_tokens: int
    output_tokens: int
    cost: float
    seconds: float
    misses: list[dict[str, Any]]


def miss(answer: Answer, got: Outcome) -> dict[str, Any]:
    """A claim the agent got wrong: what the handlers decided, and what it did."""
    return {
        "claim_id": answer.claim_id,
        "expected": answer.decision,
        "expected_payout": answer.payout,
        "got": got.decision,
        "got_payout": got.payout,
        "status": got.status,
    }


def tally(
    trial: Trial,
    repeat: int,
    outcomes: list[Outcome],
    key: dict[str, Answer],
    usage: dict[str, Any],
) -> Repeat:
    """Score a run's outcomes against the answer key, with what it used: the
    run's usage, and `wall_seconds`, the time it took from start to end."""
    pairs = [(key[got.claim_id], got) for got in outcomes]
    return Repeat(
        model=trial.model.spec,
        label=trial.model.label,
        claims=trial.claims,
        repeat=repeat,
        worked=len(outcomes),
        decisions_right=sum(decision_right(a, got) for a, got in pairs),
        payouts_right=sum(payout_right(a, got) for a, got in pairs),
        undecided=sum(got.decision is None for got in outcomes),
        model_calls=usage["model_calls"],
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        cost=usage["cost"],
        seconds=usage["wall_seconds"],
        misses=[miss(a, got) for a, got in pairs if not payout_right(a, got)],
    )


def run_repeat(trial: Trial, repeat: int, key: dict[str, Answer]) -> Repeat:
    """Reseed, work the trial's claims on its model, and score what came of it."""
    claim_ids = chosen(key, trial.claims)
    reset()
    started = time.monotonic()
    work_claims(claim_ids, trial.model)
    seconds = time.monotonic() - started
    run = api.get_latest_run()
    if run is None:
        raise RuntimeError("The claims were worked, but no run was recorded")
    usage = run["usage"] | {"wall_seconds": seconds}
    outcomes = [outcome(api.get_claim(claim_id)) for claim_id in claim_ids]
    return tally(trial, repeat, outcomes, key, usage)


def load_results(path: Path) -> list[Repeat]:
    """The runs done so far, so an interrupted comparison picks up where it was."""
    if not path.exists():
        return []
    return [Repeat(**row) for row in json.loads(path.read_text(encoding="utf-8"))]


def save_results(results: list[Repeat], path: Path) -> None:
    rows = [asdict(result) for result in results]
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
