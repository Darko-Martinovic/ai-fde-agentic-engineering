"""Run the UnderCover Agent: `uv run -m agent CLM-1001` for one claim, or
`uv run -m agent` for every waiting claim in turn."""

import sys

from agent import api
from agent.config import current_model
from agent.harness import work_claim


def waiting_claims() -> list[str]:
    """Return the ids of the claims waiting in the queue."""
    return [c["claim_id"] for c in api.list_claims() if c["status"] == "waiting"]


def main(claim_ids: list[str]) -> None:
    """Run the agent on the claims given, or on the whole queue if none are, in
    one run, finished with each claim's report."""
    model = current_model()
    claims = claim_ids or waiting_claims()
    mode = "claim" if claim_ids else "queue"
    run_id = api.start_run(mode, max(len(claims), 1), model.spec)["run_id"]
    reports = []
    for claim_id in claims:
        reports.append(work_claim(claim_id, run_id, model))
        print(reports[-1], flush=True)
    api.finish_run(run_id, "\n".join(reports))


if __name__ == "__main__":
    main(sys.argv[1:])
