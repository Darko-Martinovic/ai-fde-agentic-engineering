"""Run the UnderCover Agent: `uv run -m agent CLM-1001` for one claim, or
`uv run -m agent` for every waiting claim in turn."""

import sys
from uuid import uuid4

from agent.main import backend, run


def waiting_claims() -> list[str]:
    """Return the ids of the claims waiting in the queue."""
    with backend() as client:
        claims = client.get("/api/claims").raise_for_status().json()
    return [c["claim_id"] for c in claims if c["status"] == "waiting"]


def main(claim_ids: list[str]) -> None:
    """Run the agent on the claims given, or on the whole queue if none are."""
    for claim_id in claim_ids or waiting_claims():
        reply = run(claim_id, f"{claim_id}-{uuid4().hex[:8]}")
        print(f"{claim_id}: {reply}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
