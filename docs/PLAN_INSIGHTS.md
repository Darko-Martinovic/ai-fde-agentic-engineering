# Plan: Insights

An Insights page for the claims desk. The queue shows where each claim stands and a claim page shows the agent at work; Insights answers how the agent's work went across the queue: how many claims went straight through, how long each one took, which tools it used and which calls the backend refused, how its decisions split by claim type, and which policy sections it cited.

## Approach

- **Computed from the records we already keep.** Steps carry a time, decisions carry who made them, and payments carry who authorized them. A refused tool call is recorded as a tool result starting `Refused (`. Insights is worked out from these when it is read, so there are no new tables and nothing to keep in step, and it carries over when the store moves to Supabase.
- **One operation.** `get_insights` (`GET /api/insights`) returns everything the page shows. Like every operation it has an `operation_id`, a one-line docstring and no optional inputs.
- **Straight through** means the agent finished the claim with no handler: it declined it, or approved it and paid it itself. A referral or a payout held for sign-off is not straight through. This is the spec's goal ("handle claims straight through"), so it leads the page.
- **Time per claim** runs from the first to the last step of the claim's latest run. The backend doesn't record when a run starts, so the first step is the first thing the model did.
- **Charts in plain SVG and CSS**, with the brand's colors as CSS variables, so the dark theme comes free and no chart library is added. Approved, declined and referred are Sea Green, Coral and Marigold, the brand's order for three series.
- **Left out:** accuracy against the handlers' decisions (the backend never reads `data/evals/`, and evaluations are a later build), the model's token cost (the agent doesn't record usage yet) and tracing (observability is a later build).

### `get_insights`

| Field | What it holds |
|---|---|
| `totals` | Claims in the queue, claims the agent decided, straight through, held for sign-off, referred, waiting for a handler, tool calls, refused calls, median and longest seconds per claim, and money: claimed on the claims the agent decided, approved by the agent, paid, and held for sign-off |
| `by_type` | Per claim type, the agent's approvals, declines and referrals |
| `tools` | Per tool, its calls and how many the backend refused |
| `sections` | Per policy section the agent cited, the number of claims (a decision that cites two sections counts for each) |
| `claims` | Per claim the agent worked: type, state, the agent's decision, the start and end of its latest run, seconds, tool calls and refused calls |

---

## Phase 1: `get_insights`

**Builds:** `backend/insights.py` with the operation and its response models, tests, and a request in the Postman collection.

**Success criteria**

- [x] On a fresh database, `get_insights` returns 25 claims in the queue, zeros everywhere else, and empty lists
- [x] A test that runs CLM-1001 straight through (approve $420, pay), CLM-1002 to sign-off (approve $1,150 with a refused payment), CLM-1003 declined and CLM-1010 referred gets: 4 decided, 2 straight through, 1 held for sign-off, 1 referred, 2 waiting for a handler, and the right money
- [x] The refused `pay_claim` on CLM-1002 counts against `pay_claim` in `tools` and in CLM-1002's row
- [x] Seconds per claim come from the step times of the latest run only
- [x] A decision citing two sections counts once for each
- [x] `GET /openapi.json` lists `get_insights` with its summary
- [x] The Postman collection has `get_insights`, and newman passes against the dev backend
- [x] `npm run check:python` passes

## Phase 2: the Insights page

**Builds:** `#/insights` in the dashboard and its link in the top bar: tiles for straight through, time per claim, tool calls and claims waiting for a handler; the money; decisions by claim type as stacked bars; tools with their refusals; policy sections cited; and a table of every claim the agent worked, linking to the claim. It refreshes every five seconds, like the queue.

**Success criteria**

- [x] Vitest tests cover the page with data, the empty state before the agent has worked a claim, and an error from the backend
- [x] The stacked bars for a type add up to the claims of that type the agent decided
- [x] The page reads well in light and dark, checked in the browser with the Playwright MCP server
- [x] `npm run check:ts` passes

## Phase 3: the run timeline, a full run, and the end-to-end tests

**Builds:** a timeline of the latest run on the Insights page, a bar per claim from its first step to its last, colored by the agent's decision. The latest run is the claims whose work followed on from each other with no gap over five minutes. End-to-end tests for Insights and for the agent's steps on a claim page. A run of the agent on the whole queue, recorded in `docs/STATUS.md`.

**Success criteria**

- [ ] Vitest tests cover how the latest run is picked and the bars' positions
- [ ] An end-to-end test records steps and decisions through the API, then sees them on Insights and on the claim page
- [ ] `uv run -m agent` (or Run queue) on all 25 claims, with the results in `docs/STATUS.md`
- [ ] Screenshots of the queue and Insights after the run, in `assets/`
- [ ] `npm run check` passes
