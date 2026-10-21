"""Run the UnderCover Agent: `uv run -m agent CLM-1001` for one claim, or
`uv run -m agent` for every waiting claim in turn."""

import sys

from agent import api
from agent.harness import work_claim


def waiting_claims() -> list[str]:
    """Return the ids of the claims waiting in the queue."""
    return [c["claim_id"] for c in api.list_claims() if c["status"] == "waiting"]


def main(claim_ids: list[str]) -> None:
    """Run the agent on the claims given, or on the whole queue if none are."""
    for claim_id in claim_ids or waiting_claims():
        print(f"{claim_id}: {work_claim(claim_id)}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
