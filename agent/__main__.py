"""Work one claim with the UnderCover Agent, outside any run, as the current
version of its configuration: `uv run -m agent CLM-1001` starts a waiting claim
or carries on one left in progress. The claim graph saves its progress with the
Postgres checkpointer. Dispatches of the whole queue are started from the
dashboard, through the agent's service."""

import argparse
import sys

from agent import checkpoints
from agent.connection import Refused
from agent.harness import TRANSIENT, current_version, work_in_run


def parse(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="uv run -m agent", description=__doc__)
    parser.add_argument("claim_id", help="the claim to work, such as CLM-1001")
    return parser.parse_args(arguments)


def main(arguments: list[str]) -> None:
    """Work the claim named and print its report."""
    options = parse(arguments)
    with checkpoints.pool() as connections:
        try:
            report = work_in_run(
                options.claim_id,
                None,
                current_version(),
                checkpoints.savers(connections),
            )
        except Refused as refused:
            report = f"{options.claim_id}: {refused.detail}"
        except TRANSIENT as error:
            report = f"{options.claim_id}: still in progress ({error!r})"
    print(report, flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
