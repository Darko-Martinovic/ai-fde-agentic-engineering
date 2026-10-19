# Status

The pilot from `docs/PLAN.md` is built: all six phases are done. Insights, from `docs/PLAN_INSIGHTS.md`, is being built: phase 1 of 3 is done.

## Built

- `backend/`: UnderCover's records in SQLite, seeded from `data/` on first use, with read operations for the claims queue (each claim's state, latest decision and payment), one claim, a policy with its plan and add-ons, a customer with their claim history, the policy wording, the agent's instructions (`backend/instructions.md`) and the handlers. The backend never reads `data/evals/` or `data/security/`.
- The claim workflow (`backend/workflow.py`): `start_claim`, `record_step`, `list_steps`, `decide_claim`, `pay_claim`, `sign_off_claim` and `resolve_referral`. A claim moves from `waiting` to `in_progress`, then to `awaiting_sign_off` (approved over $1,000), `referred` or `decided`. A payment over $1,000 is refused until a handler signs off, and a referral waits for a handler to approve or decline it. Payments are recorded, not made.
- `agent/`: the UnderCover Agent. It reads the claim, the policy and the customer through the API, decides by the policy wording in its prompt, records its decision, and pays approvals of $1,000 or less. Every tool call, tool result and reply is recorded as a step. A refused payment comes back to the agent as text.
- Running the agent (`backend/runner.py`): `run_claim`, `run_queue`, `get_agent` and `stop_agent` start the agent as a separate process, one run at a time. Stop ends it at once and puts the claim being worked back to `waiting`, keeping its steps. A new run first returns any claim an earlier run left in progress.
- `dashboard/`: the claims desk, in the brand's colors with light and dark themes.
  - Queue: the agent bar (Run queue and Stop), a tile per state that filters the table, money totals, search, a type filter and a sortable table.
  - Claim: the claim in full (story, items, documents), the policy and customer, the decisions and payment, a live timeline of the agent's steps, Run and Stop, a sign-off form for payouts over $1,000, and a form for a handler to decide a referral.
  - Instructions: the agent's instructions and the policy wording.
- Insights (`backend/insights.py`): `get_insights` sums up the agent's work on the queue from the records already kept: claims decided, straight through (declined, or approved and paid by the agent), sign-offs, referrals, claims waiting for a handler, tool calls and the calls the backend refused, time per claim (first to last step of its latest run), money, decisions by claim type, tools and the policy sections cited.
- `e2e/`: Playwright tests of the queue, opening a claim, signing off a payout and deciding a referral, on their own backend (port 8001), dashboard (port 5174) and database (`e2e/undercover-e2e.db`, seeded fresh each run).
- `postman/`: a Postman collection and environment for the whole API, including a run through the workflow, the insights it adds up to, and starting and stopping the agent.

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on http://localhost:5173. The API is documented at http://localhost:8000/docs.
- The database is `backend/undercover.db`, or the file named in `UNDERCOVER_DB`. `uv run -m backend.seed` resets it to the data in `data/`.
- Run the agent from the dashboard (Run queue, or Run the agent on a claim), or from the command line with the backend running: `uv run -m agent CLM-1001` for one claim, `uv run -m agent` for every waiting claim. It calls the model in `MODEL_NAME`, or `openai/gpt-6-luna` by default; `MODEL_NAME=openrouter/free` in `.env` is free.
- `npm run check` runs every check. The end-to-end tests need ports 8001 and 5174 free.
- `npx -y newman@6 run postman/undercover.postman_collection.json -e postman/undercover_local.postman_environment.json` runs the Postman collection against the backend on port 8000. Its Workflow folder changes claims, so reset the data first, and its Agent folder calls the model for a moment.

## Live runs

- CLM-1001, run from the dashboard with GPT-6 Luna: approved and paid $420.00 under Section 3, Trip Delay, with each step shown as it arrived.
- CLM-1003, run with `uv run -m agent CLM-1003`: approved for $3,750.00 (the $3,800.00 bill less the $50.00 deductible) under Section 7, Emergency Medical, and left awaiting sign-off with no payment.
