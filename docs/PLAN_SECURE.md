# Plan: security changes before UnderCover goes on AWS

This plan builds what `docs/SECURE.md` asks for (a copy of `labs/week3day2_product_SECURE.md`, committed with this plan) on top of our improver build, in the brief's four steps, one phase each, and a fifth phase for the live checks and the documents. Each phase leaves `npm run check` green, is reviewed by a fresh subagent and goes in through its own PR on the fork before the next one starts.

SIDENOTE: For consistency with the course, please read `labs/week3day2_lab1.ipynb` and build the check in step 2 in the same style as the lab, and read `labs/week3day2_lab2.ipynb`, which deploys the app, without running it. Where the lab and this document differ, follow this document. Include this sidenote in your plan too.

When it's done, everything the agent's side sends to the backend carries the agent's key, and the backend refuses the agent's routes without it. The dashboard's routes need a signed-in handler, and the reads both use take either. A second model reads every claim before the claim agent's model does, and a claim that tries to instruct whoever handles it is referred with the check's reason. The backend serves the claim agent's eight operations as an OpenAPI document of their own for the Gateway, refuses any payment over the approval limit before it looks at the claim, and pays a claim itself when a handler signs it off. The backend and the built dashboard run as one app, on a laptop under uvicorn or on Lambda through Mangum.

Both labs were read, and neither was run for this plan (Lab 1 was run on 2026-10-29, fork PR #75). Ed's `upstream/week3day2-end` was not read, as `AGENTS.md` asks. The brief's notes describe Ed's build, which differs from ours in its module names (one `main.py`, `database.py`, `dependencies.py`, `harness.py` for the graph), its operation names (`record_decision`, `get_claim_history`) and its sign-off (no rejection). Where a note doesn't match our code, this plan follows its intent and says so.

Only phase 5 calls a real model. Its runs are estimated at about $0.06 (see phase 5).

## Before we start

Checked on 2026-10-29:

- `.env` has `DATABASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` and `HANDLER_PASSWORD`, no `MODEL_NAME`, and no `UNDERCOVER_API_KEY` yet.
- The OpenRouter key has $3.09 left of its $5 monthly limit.
- `pyproject.toml` already has the `server` group the brief mentions (FastAPI, httpx, Mangum, openrouter, psycopg, PyJWT, SQLAlchemy, uvicorn). It lacks `python-dotenv`, which the backend needs through `settings/`.
- The backend seeds itself on the first request that finds no tables (`backend/seed.py`'s `ready`, called from `backend/api.py` and `backend/signed_in.py`), not in the startup hook, which only sets the thread limit.
- `backend/` imports nothing from `agent/`, but it imports `settings`, the repo's shared settings package, which reads `settings/.env.defaults`.

## Decisions for the student

The student accepted every recommendation below on 2026-10-29.

| | Recommended | Why |
|---|---|---|
| The operation names | Rename `decide_claim` to `record_decision` and `get_customer` to `get_claim_history` (operation ids, `agent/api.py`, the claim agent's tools, `api.ts`'s keys, Postman and the tests). Paths stay as they are | The brief names the eight operations, the Gateway names its tools after them, Lab 2's challenge writes its Cedar policy for `record_decision`, and the Day 3 lab and brief use both names. Keeping ours would mean editing the labs every day |
| `settings/` in the Lambda package | The package holds `settings/` (its `__init__.py` and `.env.defaults`) beside `backend/`, `data/` and `dashboard/dist/`, and `python-dotenv` joins the `server` group. Lab 2's packaging cell then copies `settings` as well, a one-word change when we run the lab | The brief's step 4.6 needs every other setting to have a default, and ours come from `settings/.env.defaults`. Moving them into the backend would give Python two ways to read settings (`docs/CODE_STANDARDS.md` 7 and 22) |
| The rejection with a note | Keep it: the claim graph still pauses for a held payout, so a handler can reject it with a note and the agent decides again. A sign-off now pays in the backend, and the resume after it ends the graph without paying | It's our addition since Week 2 Day 3, and the brief's step 3.6 expects a pause and a resume after the sign-off. The AGENT_GUIDE says Ed's build takes the pause out, because his build has no rejection |
| The key | `secrets.token_hex(32)` (64 letters and digits), written into `.env` without printing it | The brief allows any random value of 32 characters or more, and the course guide says letters and digits are safest for AgentCore Identity on Day 2's Lab 2 |
| Where the check's instructions live | In the agent, in a module of its own (`agent/screening.py`), with the lab's instructions and its two fields word for word. The backend names the check's model (`get_screening_model`) | The brief's step 2.8 keeps the check outside the versioned configuration, and the improver only changes versions. `MODEL_NAME` stays in `backend/free_model.py` alone (2.2) |
| The full API document | `/openapi.json` and `/docs` stay open, as today | The brief doesn't ask to close them. They describe the routes and hold no data, and every route that holds data checks the key or the sign-in |

## Design

### Modules

New:

- `backend/agent_key.py`: the agent's key. FastAPI's `APIKeyHeader(KEY_HEADER, auto_error=False)` reads the `X-API-Key` header, and `secrets.compare_digest` compares it with `UNDERCOVER_API_KEY` (`is_agent`); `agent_key` refuses with a 401 ("This route needs the agent's key") unless the key is right. With no key set, every key is wrong.
- `backend/callers.py`: who may call a route, as dependencies: `AGENT` (the key), `HANDLER` (a signed-in handler) and `AGENT_OR_HANDLER` (either). FastAPI has no dependency for one of two, so `agent_or_handler` calls the sign-in's own two in turn when the key isn't there.
- `backend/agent_document.py`: the router for `GET /api/agent/openapi.json`. FastAPI's `get_openapi` over the app's routes whose `operation_id` is one of the eight, with no `servers` and no security schemes, so the Gateway sees no key input. It needs the key or a signed-in handler.
- `backend/dashboard_files.py`: serves the built dashboard when `dashboard/dist` exists: a file at its own path, `index.html` for any other path outside `/api/`, and the backend's usual JSON 404 for an unknown `/api/` path. A route outside the schema, added last, so every API route comes first.
- `backend/lambda_runtime.py`: whether the backend runs on Lambda (`AWS_LAMBDA_FUNCTION_NAME` set), which `db.py` and `seed.py` ask.
- `agent/screening.py`: the check for hidden instructions, in the lab's style: its instructions and `Screening` (reason first, then `instructions_found`) from `labs/week3day2_lab1.ipynb`, the customer's fields of a claim, and `screen_claim`, which asks the model with Structured Outputs (`include_raw=True`, for each call's cost) up to three times until it gets an answer it can read.
- `scripts/check_server_group.mjs` (or a `package.json` line): `uv run --isolated --only-group server python -c "import backend.main"`, the brief's import check, in `check:python`.

Changed:

- `agent/connection.py`: `send` adds `X-API-Key` from `UNDERCOVER_API_KEY` to every request, read as each request is sent, as the brief's note asks. Every caller (the claim agent's tools, the graph's recording, the dispatcher, the service, the improver) goes through it, so nothing else changes.
- `agent/service.py`: its startup refuses to start without `UNDERCOVER_API_KEY` and says it's missing.
- The backend's routers: each route takes the guard its caller needs (see API).
- `agent/graph.py`: a `screen` node before `agent`. START goes to `screen`. A claim it passes goes on to `agent`, and a flagged claim is referred through `record_decision` and the graph ends. A carry-on from saved progress resumes after the node, so the check runs once for each claim, and a claim started again from its first message is checked again. The `pay` node is reached only for an approval the backend can pay at once. After a sign-off the backend has paid, so the resume ends the graph.
- `backend/reviews.py`: a sign-off records the payment itself, as part of the review, and the claim is decided. It still asks the agent's service to resume the claim, as today, so the graph finishes, but nothing waits on that.
- `backend/workflow.py`: `pay_claim` refuses any amount over the approval limit with a 403 that names the limit ("A payment over $1,000.00 needs a handler's sign-off"), before it looks at the claim.
- `backend/seed.py`: seeds CLM-1901 with its policy and customer from `data/security/`, beside `data/claims.json`, and not its handler's decision. `ready` seeds nothing on Lambda.
- `backend/db.py`: on Lambda, `NullPool` and psycopg's `prepare_threshold=None`; elsewhere as today.
- `backend/main.py`: adds the two new routers, the dashboard's files when the folder exists, and `handler = Mangum(app, lifespan="off")` at the end.
- `backend/configuration.py`: `get_screening_model` (agent only): the check's model, `SCREEN_MODEL` at `SCREEN_REASONING_EFFORT` from `settings/.env.defaults` (`openai/gpt-6-luna`, `none`), or the free model with no reasoning effort when `MODEL_NAME` is set (`backend/free_model.py` answers which).
- `backend/models.py`: a `check` step kind, shown as "Security check" on the claim page.
- `dashboard/`: the claim page shows the check as the first step. `npm run build` builds into `dashboard/dist` with `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` read from `.env` when there is one and otherwise from the environment.
- `e2e/`: the test backend gets a fixed key (`E2E_API_KEY` in `settings/.env.defaults`, as `E2E_PUBLISHABLE_KEY` is), and the tests that play the agent through the API send it.
- `backend/postman/`: the agent's requests send `X-API-Key: {{apiKey}}` (`--env-var apiKey=…`), the dashboard's reads sign in, and the collection gains the agent's document, a payment over the limit and a request without the key.

### API

Every route keeps its path. The guards:

| Who calls it | Guard | Routes |
|---|---|---|
| Nobody in particular | Open | `health` |
| The agent's side only | The key (`AGENT`) | `start_claim`, `fail_claim`, `record_step`, `record_decision`, `pay_claim`, `calculate_payout`, `record_model_call`, `record_work_time`, `list_sections`, `search_documents`, `get_version`, `get_current_version`, `get_screening_model`, `create_dispatch`, `create_evaluation`, `create_round_evaluation`, `record_run_claims`, `finish_run`, `stop_runs`, and every route under `/api/rounds` |
| Both | The key or a signed-in handler | `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `read_section`, `get_agent_document` |
| The dashboard only | A signed-in handler | `list_steps`, `list_handlers`, `get_signed_in_handler`, `get_policy_wording`, `get_latest_dispatch`, `get_insights`, `get_configuration`, `get_version_details`, `get_settings`, `list_evaluations`, `get_evaluation`, `get_improvement`, `get_recipe` |
| The dashboard's actions | A signed-in handler, a senior one where they are today, never the key | `review_payout`, `decide_as_handler`, `start_dispatch`, `stop_run`, `start_evaluation`, `change_settings`, `start_round`, `stop_round`, `approve_proposal`, `reject_proposal` |

A key never stands in for a handler: a dashboard route with the key and no sign-in is refused with the sign-in's 401. A round the service records for a handler (`create_round`, `record_review`) keeps its `handler_id`, as today, behind the key.

The agent's document holds exactly `get_claim`, `get_policy`, `get_claim_history`, `search_documents`, `read_section`, `calculate_payout`, `record_decision` and `pay_claim`, each with its operation id and one-line docstring, the payment's input still named `amount`.

### The check

The node takes the claim as the claim agent's `get_claim` gives it (a copy reads as any claim) and gives the model the fields the customer wrote: the summary, the story, the dates and place, the items and the documents. The lab gave the model the policy record too; the brief asks for the claim's customer fields only, and leaves out what UnderCover wrote. The model's answer is read with Structured Outputs. A call whose answer can't be read is tried again, up to three calls in all, and each call is recorded with its tokens and cost as one of the claim's model calls, so it counts on the scoreboard. A provider error or a timeout is handled as the claim agent's own model calls are: the harness lets a rate limit or a timeout through for the dispatcher to retry, and fails the claim on any other error. After three unreadable answers the claim fails with that reason. A flagged claim is referred with a payout of $0.00, the check's reason as its reasons, and "Security check" as its section. The first step on the claim's page is the check's result, either way.

### Following the labs, and where we differ

- The check's instructions, its two fields and Luna at `none` are Lab 1's, word for word.
- Lab 2's notes about the deployment (`npm run build`, `dashboard/dist`, `backend.main.handler`, `backend.main:app`, transaction pooler on 6543, the three environment variables) all hold. The one difference is `settings/` in the package (see Decisions).
- Ed's build pays on a sign-off and takes the pause out. Ours pays on a sign-off and keeps the pause for the rejection.

### Checked against the code standards

- One way to each service (7, 15): the key is added in `agent/connection.py` alone and checked in `backend/agent_key.py` alone. `MODEL_NAME` stays in `backend/free_model.py`, and the check's model reaches the agent through `agent/api.py`'s `get_screening_model`.
- One job a module (8, 11): the key, the agent's document, the dashboard's files and the check each get a module of their own. The graph's new node calls `screening.py` and `recording.py`, as its other nodes do.
- The framework's own way (10): `APIKeyHeader` for the key, `get_openapi` for the document, Mangum for Lambda, `with_structured_output(include_raw=True)` for the check, a LangGraph node for running it once, `NullPool` for Lambda.
- `main.py` only puts the app together (17): the new routes live in their routers, and `handler` is one line.
- Configuration (22): `SCREEN_MODEL`, `SCREEN_REASONING_EFFORT` and `E2E_API_KEY` in `settings/.env.defaults`, the key in `.env`.
- Instructions as goals (14): the claim agent's instructions don't change. The check's instructions are the lab's, which say what to look for, not steps.

### How the criteria are checked

Tests run with a key the root `conftest.py` sets for the test run, and none reads `.env`. Live checks run with `npm run dev` on Supabase, signed in as a handler from Supabase Auth with `HANDLER_PASSWORD`. Browser checks go through the Playwright MCP server. Nothing calls AWS.

## Phase 1: An API key for the agent

- [x] `UNDERCOVER_API_KEY` is in `.env` (64 hex characters), added without printing it.
- [x] `agent/connection.py` sends `X-API-Key` on every request, read as each request is sent. A test checks the header reaches the backend from the claim agent's tools, the dispatcher and the improver's client.
- [x] `backend/agent_key.py` compares in constant time (`secrets.compare_digest`), and every route has the guard in the API table. A test walks the app's routes and checks each operation's guard against the table, so a new route can't be left open by mistake.
- [x] Tests: an agent route with no key, a wrong key and the right key (401, 401, 200); a shared read with the key, with a handler's sign-in and with neither (200, 200, 401); a handler action with only the key (401); the backend with no key set (it starts, a handler's routes work, every key is refused).
- [x] The agent's service refuses to start without the key, and says so; a test covers it.
- [x] `health` is open; a test covers it.
- [x] The e2e backend has `E2E_API_KEY`, the e2e tests that play the agent send it, and `npm run e2e` passes.
- [x] Postman: the agent's requests send the key, the dashboard's reads sign in, and newman passes against `npm run dev` after a reseed.
- [x] `npm run check` is green, with `.env` moved out of the way.
- [x] With `npm run dev` running: the dashboard works as before for Dana Whitfield (queue, a claim, Scoreboard, Configuration, Settings, Improvement), with no console errors, and `curl` to `POST /api/claims/CLM-1001/start` without the key gets a 401. The agent's command line and a dispatch wait for phase 5's live checks.
- [x] Reviewed by a fresh subagent; findings fixed: the header and the setting named once on each side, the guards in a module of their own (`backend/callers.py`), no header without a key, the no-key test run through the startup, and the test's stand-in for the service at `agent_service.ask`. Not taken: one Playwright request context for the agent in place of `headers: AS_THE_AGENT` on each call, which would change every spec's fixtures for no change in what they test.

## Phase 2: A check for instructions hidden in a claim

- [x] `agent/screening.py` holds the lab's instructions and `Screening`, and `screen_claim` asks the model up to three times for a readable answer.
- [x] The claim graph's first node runs the check. A flagged claim is referred with a payout of $0.00, the check's reason and "Security check" as the section, and the claim agent's model is never called; a claim it passes goes on as before.
- [x] The check runs once for each claim: a carry-on from saved progress, after a restart or a review, doesn't run it again; a claim started again on a new thread does.
- [x] Each of the check's calls, retries included, is recorded with its cost as one of the claim's model calls, and the check's result is the claim's first step, shown as "Security check" on the claim page.
- [x] `get_screening_model` gives Luna at `none`, or the free model with no reasoning effort when `MODEL_NAME` is set; `MODEL_NAME` is still read only in `backend/free_model.py` (`tests/test_standards.py`).
- [x] The check is outside the versioned configuration: no version or proposal can change it, which a test checks on `propose_change`'s input.
- [x] Seeding adds CLM-1901 with its policy and customer from `data/security/`; `data/claims.json` is unchanged; CLM-1901 is in the queue and in neither evaluation set, and no score changes.
- [x] Tests on a stub model: a claim the check flags (referred with the reason, no call to the claim agent's model), a claim it passes, an unreadable answer three times (the claim fails), a provider error, a carry-on that skips the check, and CLM-1901 in the queue and in neither set.
- [x] The claim page shows the check's step; a vitest test covers it.
- [x] `npm run check` is green.
- [x] Reviewed by a fresh subagent; findings fixed: a set's claims (those with a handler's decision in it) defined once, in `originals`, so a round's cost estimate leaves CLM-1901 out too; tests for no second check after a sign-off or a rejection, for a rate limit or a timeout from the check leaving the claim in progress, for the free model's check and for the real check's model; seeding reads `data/security/` through `SECURITY_FILES`, and `read` finds `data/` when it's called. Not taken: building the check's model only when a claim needs one (a carry-on after a review builds it and never calls it), since it costs one read and no model call.

## Phase 3: The agent's own API, and a sign-off that pays

- [ ] The renames: `record_decision` and `get_claim_history` everywhere (backend, `agent/api.py`, the claim agent's tools, `api.ts`, Postman, tests). `tests/test_standards.py` and `dashboard/src/standards.test.ts` still pass.
- [ ] `GET /api/agent/openapi.json` returns exactly the eight operations, with their operation ids and docstrings, no `servers` and no key parameter; it needs the key or a signed-in handler. Tests check the set of operations, the missing `servers`, the missing key input and `amount` on the payment.
- [ ] `pay_claim` refuses any amount over the approval limit with a 403 naming the limit, before it looks at the claim; a test pays $4,800 on CLM-1901, which was never approved, and gets the limit's 403.
- [ ] A sign-off pays the claim: the payment records the handler and the time of the sign-off, the claim is decided, and nothing in the agent pays it again. Tests: a sign-off that pays once; a repeat of the sign-off refused; an agent resumed after a sign-off that makes no payment call and ends.
- [ ] The rejection with a note works as before; its tests still pass.
- [ ] The e2e sign-off test expects the claim paid at once.
- [ ] `npm run check` is green.
- [ ] Reviewed by a fresh subagent; findings fixed.

## Phase 4: Ready for Lambda

- [ ] `npm run build` builds the dashboard into `dashboard/dist`, with the Supabase address and publishable key from `.env` when there is one and otherwise from the environment, and prints no warnings. `npm run check` still never reads `.env`.
- [ ] With `dashboard/dist` there, the backend serves it at `/`: its files at their own paths, `index.html` for any other path outside `/api/` (a dashboard page on a refresh), every `/api/` path as before and the JSON 404 for an unknown one. Without the folder, the backend runs as today and `npm run dev` is unchanged.
- [ ] `backend.main.handler` is `Mangum(app, lifespan="off")`, and the app answers every request without its startup hook; on Lambda nothing seeds the database.
- [ ] The `server` group holds what the backend imports, `python-dotenv` added, and `check:python` runs the import check in an isolated environment, leaving `.venv` alone.
- [ ] At run time the backend imports nothing outside `backend/`, `settings/` and the `server` group, reads files only from the package and writes none. A test imports the backend with `agent` blocked.
- [ ] The backend runs with only `DATABASE_URL`, `VITE_SUPABASE_URL` and `UNDERCOVER_API_KEY` set; everything else has its default in `settings/.env.defaults`.
- [ ] On Lambda (`AWS_LAMBDA_FUNCTION_NAME` set) the backend opens a connection for each request with `NullPool`, and psycopg's prepared statements are off; elsewhere the pool is as today. A test checks both.
- [ ] Tests: the Lambda handler with a Function URL event for `/api/health`, and with a stand-in dashboard build, `index.html` for `/` and for a dashboard page.
- [ ] Live: the backend started on the laptop with `AWS_LAMBDA_FUNCTION_NAME` set and `DATABASE_URL` on port 6543 serves the claims to a signed-in handler.
- [ ] Live: after `npm run build`, the backend on its own under uvicorn serves the dashboard at `http://127.0.0.1:8000`, where Dana Whitfield signs in and sees the claims, checked through the Playwright MCP server.
- [ ] The deployment package (`backend/`, `settings/`, `data/`, `dashboard/dist/` and the `server` group's Linux packages for Python 3.12), built in a temporary folder, is under 50 MB zipped; its size is reported.
- [ ] `docs/TECH_STACK.md` has a Deployment section: the build command and its folder, what goes in the package, the Lambda handler, the app a web server runs, and the environment variables.
- [ ] `npm run check` is green.
- [ ] Reviewed by a fresh subagent; findings fixed.

## Phase 5: The live checks and the documents

After one `uv run -m backend.seed`, with `npm run dev` running on the default model and `MODEL_NAME` out of `.env`. The estimate: CLM-1001 on the command line, about $0.001; a dispatch of the other 25 claims on Luna at low, with 26 checks at about $0.0001 each, about $0.03; the evaluation set's five tiny claims with the judge, about $0.01. About $0.05 in all, $0.06 with retries.

- [ ] `uv run -m agent CLM-1001` works the claim with the key, and a dispatch from the queue page works the rest as before.
- [ ] The dispatch refers CLM-1901 with the check's reason, which its claim page shows as the first step, and decides the other claims as before.
- [ ] An evaluation of the evaluation set's five tiny claims, started on the Scoreboard, flags none of them.
- [ ] Dana Whitfield signs off a held payout on the dashboard and it's paid once, at the sign-off.
- [ ] `curl` to an agent route without the key gets a 401.
- [ ] What the runs spent, from the backend's records and the OpenRouter key's usage, is reported in `docs/STATUS.md`.
- [ ] `docs/SPEC.md` (the key, the check, the sign-off that pays, CLM-1901 seeded from `data/security/`), `docs/TECH_STACK.md`, `docs/PROCESS.md`, `docs/STATUS.md`, `docs/CODE_STANDARDS.md` (the new modules in 13 and 15) and `data/README.md` describe the product as it now is.
- [ ] The whole branch is reviewed against `main` by a fresh subagent; findings fixed.
- [ ] `npm run check` is green, with `.env` moved out of the way.
- [ ] `week3day2-end` is cut from `main` after the last merge and locked like the earlier end branches, and `CLAUDE.md` lists it.

## Not in this plan

- Anything on AWS: Lab 2 deploys the app and creates the Gateway and the Policy, on its own day's run.
- The claim agent on the Gateway's tools, the context layer and Memory (Day 3), and the agent's service off the laptop (Day 4).
- Closing `/openapi.json` and `/docs`.
