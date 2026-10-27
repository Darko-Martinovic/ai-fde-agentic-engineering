"""Running a trial once: an evaluation of the queue's labelled claims on the
trial's model, started through the backend like one from the Scoreboard, and
its outcome as the backend scored it."""

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from bench import backend
from bench.plan import Trial

RESULTS = Path(__file__).with_name("results.json")
# The labelled set a comparison evaluates: the 25 claims of the queue
EVALUATION_SET = "evaluation"
# How often to look whether the evaluation has finished, and how long the
# agent's service may take to record it, in seconds
POLL_SECONDS = 5
APPEAR_SECONDS = 60
RUNNING, FINISHED = "running", "finished"


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
    # Claim agents at once; runs before the Scoreboard worked one at a time
    agents: int = 1

    @property
    def refused(self) -> bool:
        """The provider answered no model call, as a free model's rate limit
        does: the run says nothing about the model, so it isn't scored."""
        return self.worked > 0 and self.model_calls == 0


def miss(copy: dict[str, Any]) -> dict[str, Any]:
    """A claim the agent got wrong: what the handlers decided, and what it did."""
    return {
        "claim_id": copy["copy_of"],
        "expected": copy["handler_decision"],
        "expected_payout": copy["handler_payout"],
        "got": copy["decision"],
        "got_payout": copy["payout"],
        "status": copy["status"],
    }


def tally(trial: Trial, repeat: int, evaluation: dict[str, Any]) -> Repeat:
    """A run of a trial, from its evaluation as the backend scored it: the
    claims right, as its measures count them, and the seconds of every claim's
    work added up."""
    copies, usage = evaluation["claims"], evaluation["usage"]
    measures = evaluation["measures"]
    return Repeat(
        model=trial.model.spec,
        label=trial.model.label,
        claims=trial.claims,
        repeat=repeat,
        worked=len(copies),
        decisions_right=round(measures["decision_accuracy"] * len(copies)),
        payouts_right=round(measures["accuracy"] * len(copies)),
        undecided=sum(c["decision"] is None for c in copies),
        model_calls=usage["model_calls"],
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        cost=usage["cost"],
        seconds=measures["seconds_per_claim"] * len(copies),
        misses=[miss(c) for c in copies if not c["right"]],
        agents=trial.agents,
    )


def started_after(run_id: int) -> int:
    """The id of the evaluation started after `run_id`, once the agent's
    service has recorded it."""
    deadline = time.monotonic() + APPEAR_SECONDS
    while time.monotonic() < deadline:
        newest = next(iter(backend.list_evaluations()), {"run_id": 0})["run_id"]
        if newest > run_id:
            return newest
        time.sleep(POLL_SECONDS)
    raise RuntimeError("The agent's service didn't start the evaluation")


def finished(run_id: int) -> dict[str, Any]:
    """Wait for an evaluation to end, and return it; one that stopped partway
    says nothing about the model."""
    while (evaluation := backend.get_evaluation(run_id))["status"] == RUNNING:
        time.sleep(POLL_SECONDS)
    if evaluation["status"] != FINISHED:
        raise RuntimeError(f"Evaluation {run_id} stopped before it finished")
    return evaluation


def run_repeat(trial: Trial) -> dict[str, Any]:
    """Evaluate the trial's claims on its model, and return the evaluation once
    it ends."""
    before = next(iter(backend.list_evaluations()), {"run_id": 0})["run_id"]
    backend.start_evaluation(
        EVALUATION_SET, trial.claims == "tiny", trial.agents, trial.model.spec
    )
    return finished(started_after(before))


def load_results(path: Path) -> list[Repeat]:
    """The runs done so far, so an interrupted comparison picks up where it was."""
    if not path.exists():
        return []
    return [Repeat(**row) for row in json.loads(path.read_text(encoding="utf-8"))]


def save_results(results: list[Repeat], path: Path) -> None:
    rows = [asdict(result) for result in results]
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
