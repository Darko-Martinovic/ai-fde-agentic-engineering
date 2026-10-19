# Status

The pilot is being built from `docs/PLAN.md`. Phases 1 to 3 of 6 are done.

## Built

- `backend/`: UnderCover's records in SQLite, seeded from `data/` on first use, with read operations for the claims queue, one claim, a policy with its plan and add-ons, a customer with their claim history, the policy wording, the agent's instructions (`backend/instructions.md`) and the handlers. The backend never reads `data/evals/` or `data/security/`.
- The claim workflow (`backend/workflow.py`): `start_claim`, `record_step`, `list_steps`, `decide_claim`, `pay_claim`, `sign_off_claim` and `resolve_referral`. A claim moves from `waiting` to `in_progress`, then to `awaiting_sign_off` (approved over $1,000), `referred` or `decided`. A payment over $1,000 is refused until a handler signs off, and a referral waits for a handler to approve or decline it. Payments are recorded, not made.
- `agent/`: the UnderCover Agent. It reads the claim, the policy and the customer through the API, decides by the policy wording in its prompt, records its decision, and pays approvals of $1,000 or less. Every tool call, tool result and reply is recorded as a step. A refused payment comes back to the agent as text.
- Running the agent (`backend/runner.py`): `run_claim`, `run_queue`, `get_agent` and `stop_agent` start the agent as a separate process, one run at a time. Stop ends it at once and puts the claim being worked back to `waiting`, keeping its steps.
- `dashboard/`: still one page that shows whether the backend is up.
- `e2e/`: one test of that page.
- `postman/`: a Postman collection and environment for the API, including a run through the workflow and starting and stopping the agent.

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173. The API is documented at http://localhost:8000/docs.
- The database is `backend/undercover.db`, or the file named in `UNDERCOVER_DB`. `uv run -m backend.seed` resets it to the data in `data/`.
- `uv run -m agent CLM-1001` runs the agent on one claim, and `uv run -m agent` on every waiting claim. It needs the backend running and calls the model in `MODEL_NAME`, or `openai/gpt-6-luna` by default.
- `npm run check` runs every check.
