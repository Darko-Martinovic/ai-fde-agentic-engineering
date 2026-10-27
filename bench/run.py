"""Running a trial once: a fresh database, the claims worked through the harness
one at a time in a dispatch of their own, and what came of them, read through
the API."""

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agent import api, checkpoints, harness
from agent.config import Model
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

    @property
    def refused(self) -> bool:
        """The provider answered no model call, as a free model's rate limit
        does: the run says nothing about the model, so it isn't scored."""
        return self.worked > 0 and self.model_calls == 0


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


def work_claims(claim_ids: list[str], model: Model) -> dict[str, Any]:
    """Work the claims one at a time on a model, in a dispatch of one claim agent
    that takes only them, and return the finished dispatch."""
    run_id = api.create_dispatch(1, model.spec, model.reasoning_effort)["run_id"]
    api.record_run_claims(run_id, claim_ids)
    try:
        with checkpoints.pool() as connections:
            for claim_id in claim_ids:
                harness.work_in_run(
                    claim_id, run_id, model, checkpoints.savers(connections)
                )
    finally:
        finished = api.finish_run(run_id, False)
    return finished


def run_repeat(trial: Trial, repeat: int, key: dict[str, Answer]) -> Repeat:
    """Reseed, work the trial's claims on its model, and score what came of it."""
    claim_ids = chosen(key, trial.claims)
    reset()
    started = time.monotonic()
    run = work_claims(claim_ids, trial.model)
    seconds = time.monotonic() - started
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
