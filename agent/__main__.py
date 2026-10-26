"""Run the UnderCover Agent. `uv run -m agent` works the waiting claims with the
queue agent, `--cap 5` stopping it at five; `uv run -m agent CLM-1001` works
one claim; and `--model provider:model` picks a model from models.toml. Each
claim graph saves its progress with the Postgres checkpointer."""

import argparse
import sys

from agent import api, checkpoints
from agent.config import Model, current_model, model
from agent.harness import work_claim
from agent.queue_agent import run_queue
from agent.tools import waiting_claims


def positive(text: str) -> int:
    """Read a cap: a whole number of claims, one or more."""
    number = int(text)
    if number < 1:
        raise argparse.ArgumentTypeError("the cap must be 1 or more")
    return number


def parse(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="uv run -m agent", description=__doc__)
    parser.add_argument("claims", nargs="*", help="claims to work; none for the queue")
    parser.add_argument(
        "--cap",
        type=positive,
        help="the most queue claims to work; every waiting one if left out",
    )
    parser.add_argument(
        "--model", help="a model in models.toml; MODEL_NAME if left out"
    )
    return parser.parse_args(arguments)


def work_claims(claim_ids: list[str], chosen: Model) -> None:
    """Work the claims named, in one run, finished with each claim's report."""
    with checkpoints.saver() as saver:
        run_id = api.start_run("claim", len(claim_ids), chosen.spec)["run_id"]
        reports = []
        for claim_id in claim_ids:
            try:
                reports.append(work_claim(claim_id, run_id, chosen, saver))
            except api.Refused as refused:
                reports.append(f"{claim_id}: {refused.detail}")
            print(reports[-1], flush=True)
        api.finish_run(run_id, "\n".join(reports))


def main(arguments: list[str]) -> None:
    """Work the claims named, or the queue with the queue agent."""
    options = parse(arguments)
    chosen = model(options.model) if options.model else current_model()
    if options.claims:
        work_claims(options.claims, chosen)
        return
    waiting = len(waiting_claims())
    if waiting == 0:
        print("No claims are waiting.")
        return
    cap = waiting if options.cap is None else options.cap
    with checkpoints.saver() as saver:
        print(run_queue(cap, chosen, saver), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
