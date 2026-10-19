# Plan: the claims pilot

The pilot from `docs/SPEC.md`: a backend that holds UnderCover's records and enforces the rules, the UnderCover Agent that decides claims through the backend's API, and a dashboard where the handlers watch the queue, read decisions, follow the agent as it works, read its instructions and sign off large payouts.

## Approach

- **The backend owns the rules.** The $1,000 sign-off limit is enforced in the payment operation, not in the agent's instructions, so a payment over the limit is refused even if the agent tries to pay. The agent's instructions only make it less likely to try.
- **The agent sees only the API.** It reads claims, policies, customers, the policy wording and its own instructions through backend operations, and it records its decision and payment the same way. The backend seeds from `data/` but never reads `data/evals/` or `data/security/`, so neither the answer key nor the security claim can reach the agent.
- **Steps are recorded as the agent works.** `run()` streams the agent and posts each tool call, tool result and reply to the backend. The dashboard polls for them, so a handler can watch a claim live without websockets.
- **Simple storage.** SQLite through Python's standard `sqlite3` module, in one file (`backend/undercover.db`, already ignored by `.gitignore`). The path comes from the environment variable `UNDERCOVER_DB` when set, so tests and the end-to-end run each use their own database. Records keep the shape they have in `data/`, stored as JSON next to the columns the backend queries (ids and status).
- **The agent runs from the command line.** `uv run -m agent CLM-1001` decides one claim and `uv run -m agent` works through every waiting claim. The dashboard watches; it does not start runs (see Open questions).

### Claim states

| State | Meaning | Set by |
|---|---|---|
| `waiting` | In the queue, not started | Seeding (`open` in `data/claims.json`) |
| `in_progress` | The agent is working on it | `start_claim` |
| `awaiting_sign_off` | Approved with a payout over $1,000; payment held | `decide_claim` |
| `decided` | Approved and paid, declined, or referred | `decide_claim`, `pay_claim` or `sign_off_claim` |

A referral is final for the pilot: it is decided, with the reasons saying what is needed, and it goes back to the handlers outside the system.

### API operations

Every operation has an `operation_id`, a one-line docstring and no optional inputs.

| Operation | Method and path | Purpose |
|---|---|---|
| `health` | `GET /api/health` | Exists already |
| `list_claims` | `GET /api/claims` | The queue: id, type, customer name, amount claimed, submitted date, state |
| `get_claim` | `GET /api/claims/{claim_id}` | The full claim with its decision and payment |
| `get_policy` | `GET /api/policies/{policy_id}` | The policy with its plan's limits and its add-ons' details |
| `get_customer` | `GET /api/customers/{customer_id}` | The customer and their claim history |
| `get_policy_wording` | `GET /api/policy-wording` | The policy wording as Markdown |
| `get_instructions` | `GET /api/instructions` | The agent's instructions as Markdown |
| `list_handlers` | `GET /api/handlers` | The three handlers, for sign-off |
| `start_claim` | `POST /api/claims/{claim_id}/start` | `waiting` to `in_progress` |
| `record_step` | `POST /api/claims/{claim_id}/steps` | Adds one step: thread id, kind (`tool_call`, `tool_result`, `reply`) and text |
| `list_steps` | `GET /api/claims/{claim_id}/steps` | The steps in order |
| `decide_claim` | `POST /api/claims/{claim_id}/decision` | Decision (`approve`, `decline`, `refer`), payout, reasons, policy section |
| `pay_claim` | `POST /api/claims/{claim_id}/payment` | Takes the amount; refused unless the claim is approved, unpaid, at or under the limit, and the amount equals the approved payout |
| `sign_off_claim` | `POST /api/claims/{claim_id}/sign-off` | Takes a handler id; releases the held payment and moves the claim to `decided` |

---

## Phase 1: Backend records

**Builds:** the SQLite schema, seeding from `data/`, and the read operations: `list_claims`, `get_claim`, `get_policy`, `get_customer`, `get_policy_wording`, `get_instructions` and `list_handlers`. The agent's first instructions go in `backend/instructions.md`, served by `get_instructions`.

**Why first:** everything else reads these records. Getting the shapes right here sets the types the agent tools and the dashboard use.

**Seeding:** on startup, if the database has no claims, the backend loads `claims.json`, `policies.json`, `customers.json`, `plans.json`, `handlers.json`, `company.json` and `policy_wording.md`. Deleting the database file resets everything. `uv run -m backend.seed` does the same reset from the command line.

**Success criteria**

- [ ] `uv run pytest backend --no-cov` passes, with tests for every read operation, a 404 for an unknown claim, policy and customer, and seeding running only once
- [ ] A test checks that seeding reads only the seven files above, so `data/evals/` and `data/security/` are never opened
- [ ] `GET /api/claims` returns 25 claims, all `waiting`, each with the customer's name
- [ ] `GET /api/claims/CLM-1001` returns the story, three items, four documents and no decision
- [ ] `GET /api/policies/POL-2001` returns the Premium plan with its limits, including the $50 deductible
- [ ] `GET /api/customers/CUS-3001` returns one previous claim, CLM-0412
- [ ] `GET /api/policy-wording` starts with `# UnderCover Travel Insurance: Policy Wording`
- [ ] `GET /openapi.json` shows every operation with its `operation_id` and summary
- [ ] `npm run check:python` passes

## Phase 2: Backend workflow and the payment rule

**Builds:** `start_claim`, `record_step`, `list_steps`, `decide_claim`, `pay_claim` and `sign_off_claim`, with the state changes in the table above and a `payments` table that records each payment (no real money moves).

**Why now:** this is where the spec's hard rule lives. Building and testing it before the agent exists proves the rule holds whatever the agent does.

**Rules enforced:**

- `decide_claim` needs the claim `in_progress`. A decline or a referral has a payout of 0. An approval over the limit in `company.json` ($1,000) goes to `awaiting_sign_off`; an approval at or under it stays `in_progress` until `pay_claim`; a decline or a referral goes straight to `decided`.
- `pay_claim` returns 409 for a claim that is not approved, already paid, over the limit, or paid an amount other than the approved payout.
- `sign_off_claim` returns 409 unless the claim is `awaiting_sign_off`, and 404 for an unknown handler. It records the payment with the handler's id.

**Success criteria**

- [ ] Tests cover every transition in the state table and every 409 above
- [ ] A test approves a claim with a $1,150 payout, calls `pay_claim` with $1,150 and gets 409, with no payment recorded; after `sign_off_claim` with `HND-01` the claim is `decided` and one payment of $1,150 is recorded against `HND-01`
- [ ] A test approves a $420 claim and pays it; a second `pay_claim` returns 409
- [ ] A test checks that exactly $1,000.00 pays without sign-off and $1,000.01 needs it
- [ ] Steps come back from `list_steps` in the order they were recorded
- [ ] `npm run check:python` passes

## Phase 3: The UnderCover Agent

**Builds:** the agent in `agent/`, replacing the hello-world tools.

- **Tools**, each a thin call to one backend operation: `get_claim`, `get_policy`, `get_customer`, `decide_claim` and `pay_claim`.
- **System prompt:** `run()` fetches the instructions and the policy wording from the API and joins them. The wording is short enough to sit in the prompt, so the agent always has it and never has to remember to look it up.
- **Instructions** (`backend/instructions.md`): read the claim, the policy and the customer's history; check every item against the wording; work out the payout by section 10; decide; explain in two or three sentences, naming the section; pay only an approval of $1,000 or less. No claims manual, as the spec says.
- **`run(claim_id, thread_id)`** calls `start_claim`, streams the agent with `thread_id` in its config, and posts each step to `record_step`.
- **Command line:** `uv run -m agent CLM-1001` runs one claim; `uv run -m agent` runs every `waiting` claim in turn. Each run gets a new thread id.

**Why this design:** the backend decides what is allowed and the agent decides what is right. Keeping each tool to one API call means the dashboard, the tests and the agent all see the same operations.

**Success criteria**

- [ ] Agent tests use a stub model (no model calls) and the real backend in process, on a temporary database
- [ ] A stub run on CLM-1001 that reads the claim, approves $420 and pays it leaves the claim `decided`, paid, with every tool call and the final reply in `list_steps`
- [ ] A stub run that approves CLM-1002 for $1,150 and then calls `pay_claim` leaves the claim `awaiting_sign_off` with no payment; the tool returns the backend's refusal to the model instead of crashing the run
- [ ] A test checks the system prompt holds both the instructions and the policy wording
- [ ] A test of the command line runs one claim and the whole queue with the stub model
- [ ] `MODEL_NAME` still overrides the default model (existing test kept)
- [ ] `npm run check:python` passes

## Phase 4: Dashboard, the queue and the instructions

**Builds:** the dashboard's layout in the brand (Instrument Sans, Instrument Serif and JetBrains Mono from Google Fonts; the palette and surfaces in `docs/BRAND.md`, in light and dark mode), the queue page and the instructions page. Navigation uses the URL hash (`#/`, `#/claims/CLM-1001`, `#/instructions`), so no router library is needed.

- **Queue:** a count for each state, then a table of claims with id, type, customer, amount claimed, submitted date and a state badge. The states use Sea Green, Marigold, Coral and Cerulean, darkened for text on light backgrounds as the brand asks. It refreshes every few seconds so a running agent shows up. Each row opens the claim.
- **Instructions:** the agent's instructions, read only, with the policy wording below them in a collapsed section.

**Why here:** the queue and the instructions read operations that already work, so the layout and the brand settle before the more involved claim page.

**Success criteria**

- [ ] Vitest tests, with `fetch` stubbed, cover the counts, the table rows, the state badges, the empty and error states, and the instructions page
- [ ] In the browser through the Playwright MCP server, with `npm run dev` running: the queue shows 25 claims, all Waiting, and the instructions page shows the text from `backend/instructions.md`
- [ ] Screenshots in light and dark mode match the brand: fonts, page background, rounded panels with no outline, no one-edge borders, amounts like $1,150.00
- [ ] The page works at phone width without scrolling sideways
- [ ] `npm run check:ts` passes

## Phase 5: Dashboard, the claim page

**Builds:** the claim page.

- The claim in full: summary, story, items, documents, the policy with its plan, and the customer's earlier claims.
- The decision: approve, decline or refer, the payout, the reasons and the policy section, and the payment once made.
- The agent's steps in order, refreshing every two seconds while the claim is `in_progress`.
- For a claim `awaiting_sign_off`: a handler picker and a Sign off button that calls `sign_off_claim` and shows the payment.

**Success criteria**

- [ ] Vitest tests cover a waiting claim, a decided claim with its reasons and section, a claim with steps, the refresh while in progress, and a sign-off that shows the payment
- [ ] In the browser: CLM-1001 shows its story, three items and four documents
- [ ] In the browser, after approving CLM-1002 for $1,150 through the API: the page shows Awaiting sign-off, signing off as Dana Whitfield moves it to Decided with a $1,150.00 payment, and the queue's counts change to match
- [ ] `npm run check:ts` passes

## Phase 6: End-to-end tests and a live run

**Builds:** Playwright tests on their own database and ports, a live agent run, and the docs.

- `playwright.config.ts` starts the backend on port 8001 with `UNDERCOVER_DB` pointing at a fresh test database, and the dashboard on port 5174 with its `/api` proxy pointed at 8001, so the tests never touch the development data or reuse the servers from `npm run dev`.
- End-to-end tests: the queue loads with 25 claims; a claim page opens from the queue; the sign-off flow, with the decision set up through the API in the test so no model is called.
- `docs/STATUS.md` describes what is built, how to run it, how to run the agent and how to reset the data.

**Why last:** these tests check the parts working together, and the live run is the first real test of the agent's instructions.

**Success criteria**

- [ ] `npm run e2e` passes, and passes again on a second run (the database starts fresh each time)
- [ ] With `npm run dev` running, `uv run -m agent CLM-1001` runs on the real model. The claim page shows each step as it arrives, then a decision with two or three sentences of reasons and a policy section
- [ ] `uv run -m agent CLM-1003` (claimed $3,800) ends in a state that follows the rules: `awaiting_sign_off` with no payment if approved over $1,000, otherwise `decided`
- [ ] `docs/STATUS.md` is up to date
- [ ] `npm run check` passes

The two live runs call the model in `MODEL_NAME`, or `openai/gpt-6-luna` by default, and cost a few cents. With `MODEL_NAME=openrouter/free` in `.env` they are free.

---

## Not in the pilot

From the spec: the claims manual, sign-in, real payments and messages to customers. Also left out until a later brief asks for them: scoring the agent against `data/evals/`, `data/knowledge.json` (the news and events feed) and the security claim in `data/security/`.

## Open questions

1. **Starting the agent from the dashboard.** The spec asks the team to *see* the queue and the agent's work, not to start it, so the plan runs the agent from the command line. A Run button on the claim page would need the backend to start agent runs in the background; it's a small addition if you want it.
2. **Referred claims.** The plan treats a referral as decided, with the reasons saying what is needed. If handlers should pick referrals up in the dashboard, that needs a further state and an action, which the spec doesn't describe yet.
