# Plan: an improver for the claim agent, and handlers who sign in

This plan builds what `docs/IMPROVE.md` asks for (a copy of `labs/week2day5_product_IMPROVE.md`, committed with this plan) on top of our swarm build, in seven phases. Each phase leaves `npm run check` green, is reviewed by a fresh subagent and goes in through its own PR on the fork before the next one starts.

SIDENOTE: For consistency with the course, please read `labs/week2day5.ipynb` and build the judge, the configuration's versions and the improver in the same style as the lab. Where the lab and this brief differ, follow the brief. Include this sidenote in your plan too.

When it's done, handlers sign in to the dashboard through Supabase Auth, and the backend checks the signed-in handler on every action. The claim agent's instructions, model and reasoning effort are kept in versions, and every dispatch and evaluation records the version it used. Jev grades each evaluated claim's explanation against the handler's reason. On a new Improvement page a senior handler runs rounds of the improver, a second agent that follows a recipe: it reads the results, proposes a new version, waits for approval, asks for its evaluations, and proposes a better recipe. The backend keeps or rolls back each version by the business's rule, within a spending limit for each round. A Settings page holds the approval limit, the objectives, the noise and tolerance, the spending limit and the agents at once. A Configuration page replaces the Instructions page. The whole dashboard is brought up to the standard of enterprise software, in light and dark mode.

Ed's `upstream/week2day5-end` was read before this plan was written: its `docs/PLAN_IMPROVE.md` and the shape of its code. His build starts from his swarm, which differs from ours (one `main.py`, no rejection, no Stop on the dashboard, no model picker, no `bench/`). This plan follows his design where it fits our code and says where it differs.

Phase 7 is the only one that runs the claim agent or the improver on the real model. Phase 4 calls the real judge on the lab's four test explanations and on five claims played out through the API, for well under a cent.

## Before we start

Checked on 2026-10-27:

- Supabase Auth has the three handlers as confirmed users, sign-ups are off, and the project signs with ES256 keys at `/auth/v1/.well-known/jwks.json`.
- `.env` has `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` and `HANDLER_PASSWORD`.
- The OpenRouter key has a $5 monthly limit, with $3.88 left.
- `pyproject.toml` already lists `openrouter` and `pyjwt[crypto]` in the dev group, for the labs. Phase 1 adds `pyjwt[crypto]` and phase 4 adds `openrouter` to the product's dependencies.

## Decisions for the student

The student asked on 2026-10-28 for the plan to be built as written, which takes every recommendation below.

| | Recommended | Why |
|---|---|---|
| `MODEL_NAME` | Follow the brief: it means only "a student on free models". Take it out of `settings/.env.defaults`, and take the `MODEL_NAME=anthropic:claude-haiku-5-5` line out of your `.env` before phase 7 | Otherwise Haiku becomes the only model allowed and the judge is never called. The claim agent's model now comes from the version |
| The model picker | Remove it from the dispatch and evaluation forms | The brief says a dispatch, and an evaluation started on the Scoreboard, always use the current version. The improver now changes the model, through an approved version |
| The model list | One file, `data/models.json`, as the brief asks: the lab's three models allowed, with their reasoning efforts, prices and build options (Luna's `max_tokens` 16000). It is seeded into `models_allowed`, and `settings/models.toml` goes | Two lists would drift apart. Anthropic and Ollama leave the product, apart from `MODEL_NAME` on free models |
| `bench/` | Retire it: delete the package, its tests and `npm`/docs mentions, and keep `bench/results.md` in git history | It ran evaluations on any model, which a versioned configuration rules out. The Configuration page now compares versions and their models on held-out scores |
| The handler's rejection | Keep it, as a senior action like the sign-off: only a handler who can sign off over the limit can review a held payout either way | It is our extra since Week 2 Day 3, and the brief's limit rule fits both halves of a review |
| A handler's decision on a referred claim | Needs a signed-in handler; an approval over the limit needs a senior one | The same limit rule as a sign-off |
| The graceful Stop of a dispatch | Keep it; any signed-in handler can stop | It is our extra since Week 2 Day 4 |
| The dashboard's files | Move pages into `dashboard/src/pages/` and shared parts into `dashboard/src/components/` in phase 1, with no change in behaviour | About 15 new pages and components arrive, and `src/` already has 54 files |
| Not in this build | The short policy wording as a lever (my Week 2 Day 5 challenge) | The brief fixes the configuration as instructions, model and reasoning effort |

## Design

### Modules

The backend:

- `db.py`: at 293 lines, it splits into `db.py` (the engine and the claims' tables) and `db_improvement.py` (the new tables). `handlers` gains `email`; `handler_decisions` gains `reason` and `reference`, which seeding reads from `data/evals/` (the brief allows opening it for this). New tables: `platform_settings` (one row per change), `models_allowed`, `versions`, `recipes`, `rounds`, `proposals`, `improver_calls` and `grades`. `runs` gains `version` and `round_id`.
- `seed.py`: version 1 of the configuration from `backend/instructions/claim.md` with `openai/gpt-6-luna` at `low`; version 1 of the recipe from `backend/instructions/recipe.md`, the lab's first recipe; the first settings row from `data/company.json` (the approval limit) and `data/improvement.json` (the rest); `models_allowed` from `data/models.json`. With `MODEL_NAME` set, version 1 and the only model allowed are that model at `default`, priced 0.
- `auth.py` (new): checks a Supabase access token. It reads `VITE_SUPABASE_URL` once, keeps one `PyJWKClient`, and returns the token's email when it is signed by one of the project's keys, has the audience `authenticated` and hasn't expired.
- `api.py`: gains `SignedIn` (401 without a valid token, 403 when no handler has the email) and `senior(action)`, which refuses a handler who can't sign off over the limit with a 403 naming the action and the handler, such as "Only a handler who can sign off payouts over $1,000.00 can change the settings. Marcus Oyelaran can't."
- `free_model.py` (new): `free_model()`, the model in `MODEL_NAME` or none. The only reader of `MODEL_NAME` in the product.
- `handlers.py` (new router): `get_signed_in_handler`, and `list_handlers`, moved from `records.py`. (Built: `list_handlers` stays, since a decision, a sign-off and a payment name the handler by id and the claim page needs their names.)
- `configuration.py` (new router): the versions, for the claim agent and the Configuration page. `store/versions.py` (new).
- `platform_settings.py` (new router): the settings and the models allowed, for the Settings page. `store/platform_settings.py` (new). (Named so as not to shadow the `settings` package.)
- `diffs.py` (new): the lines that differ between two texts, from `difflib.unified_diff` with two lines of context, as the lab's `show_changed_lines`. For versions and recipes.
- `judge.py` (new): Jev through OpenRouter's Decisions endpoint with the `openrouter` package and the lab's rubric and three questions. The only module that calls the judge or knows its address, `JUDGE_URL` in `settings/.env.defaults`. `store/grades.py` (new).
- `verdict.py` (new): the lab's `compare` and `keep_or_roll_back` as plain functions of two sets of scores and the round's settings, like `scoring.py`.
- `spending.py` (new): what a round has spent and an evaluation's estimate.
- `version_scores.py` (new): a version's scores from the whole-set evaluations its rounds ran, which `configuration.py` and the rounds both need.
- `improvement.py` (new router): what the dashboard reads and does under `/api/improvement`. `rounds.py` (new router): what only the agent's service writes under `/api/rounds`. `store/rounds.py` (new): rounds, proposals, recipes and improver calls.
- `runs.py` and `evaluations.py`: the version on every run; `create_round_evaluation`; `finish_run` grades an evaluation and stops one cut short by its round. `start_dispatch`, `start_evaluation` and `stop_run` need a signed-in handler.
- `reviews.py`: `review_payout` records the signed-in handler, with `senior`; `decide_as_handler` likewise for an approval over the limit.
- `claim_rules.py` and `workflow.py`: the approval limit from the current settings when a decision is recorded, and each decision records the limit it was held under.
- `agent_service.py`: gains `start_round` and `review_proposal`.
- `documents.py`: `get_instructions` goes, replaced by the versions.
- `agent_models.py` goes: `list_models` is replaced by the models allowed in `get_settings`.

Inside the backend no router imports another; `judge`, `verdict`, `diffs`, `spending`, `version_scores` and `scoring` import nothing from the routers.

The agent, in six parts (`docs/CODE_STANDARDS.md` 13 changes):

- `connection.py` (new): the backend's address, the one `httpx` client with its retries, `Refused` and the function that sends a request. `api.py` and `improver_api.py` both use it, so the address is written once.
- `api.py`: gains `get_version` and `get_current_version`; `create_dispatch` and `create_evaluation` lose the model, which the backend takes from the version; `get_instructions` goes. Still nothing that reads scores, grades, settings, rounds or the handlers' decisions.
- `improver_api.py` (new): one function per operation under `/api/rounds`, and `create_round_evaluation`.
- `tools.py`, `graph.py`: unchanged.
- `harness.py`: builds the claim agent from a version: the model from `models_allowed` at the version's reasoning effort (`default` sends none) and the version's instructions followed by the documents' contents, as today. `uv run -m agent CLM-1001` and a resume after a review use the current version.
- `config.py` goes with `settings/models.toml`.
- `dispatcher.py`: as today. `work_run` runs the graph in a fresh `contextvars.Context`, so it is a root run wherever it is called, including inside the improver's tool.
- `improver.py` (new, the sixth part): the improver, a LangChain `create_agent`, with its context, its four tools, its middleware and `work_stretch`, which runs it until it waits for a handler or ends.
- `rounds.py` (new, a support of the service): a round's work, its first evaluations, its stretches and its finish. `service.py` stays under 300 lines.
- `service.py`: builds each run's claim agents from its version; gains `start_round` and `review_proposal`; the one-run lock names what holds it.
- `tracing.py`: a round's improver traces in one session; its evaluations' claims tagged with the round as well as the run.

`service` uses `rounds`, `dispatcher`, `harness` and `api`; `rounds` uses `improver`, `dispatcher` and `improver_api`; `improver` uses `improver_api` and reaches claim agents only through the function the service hands it. `tools`, `graph` and `harness` never import `improver_api` (a test checks it).

The dashboard:

- `auth.ts` (new): the only module that uses `@supabase/supabase-js`: `signIn`, `signOut`, the access token and a way to follow sign-ins.
- `api.ts`: a function for each new operation, with the access token on every request.
- `handler.ts` and `components/RequireHandler.tsx` (new): the signed-in handler in a React context, and the guard that sends a visitor to the sign-in page and back.
- `theme.ts` (new): light, dark or the computer's, in `localStorage`, set as `data-theme` before the first render.
- New pages: sign-in, Configuration, a version, Settings, Improvement, a recipe. New components: `PageHeader`, `ConfirmDialog` (a `<dialog>` with `showModal()`), `DiffView`, `StateMessage`, `NotAllowed`, `GradeChip`, `RoundProgress` and `VersionChart` (SVG, no new library).
- `HandlerPicker.tsx` and `handlers.ts` go; `Instructions.tsx` gives way to the Configuration page.

### Sign-in

- On `#/sign-in`, `signInWithPassword` with email and password; no sign-up. Every other page needs a signed-in handler and comes back after signing in. The header shows the handler's name and role, and Sign out.
- The backend checks the token on every handler action: `review_payout`, `decide_as_handler`, `start_dispatch`, `stop_run`, `start_evaluation`, `start_round`, `stop_round`, `approve_proposal`, `reject_proposal`, `change_settings`, and on `get_signed_in_handler`. Reads stay open, as the agent's service reads without signing in until Week 3.
- `data/handlers.json`: `can_approve_over_limit` false for Marcus Oyelaran and Priya Raman. Seeding stores each email.
- A handler who can't do something sees why and no button for it; the backend refuses it with the same words.
- Vite: `envDir` is the repo root in `development` mode only. Vitest and the e2e run set their own values, so `npm run check` never reads `.env`. (Built the way `VITE_MAX_AGENTS` already was: `vite.config.ts` defines both from `settings/settings.config.ts`, which reads `.env` for `npm run dev` only; Vitest leaves them empty and stands in for `auth.ts`, and the e2e run sets them to the Auth stand-in.)

### The configuration in versions

- A version: number, instructions, model, reasoning effort, `based_on` (the current version when it was proposed, and what its diff is from), reason, who proposed it (a round, or "The claims team" for version 1), who approved it and when, and its verdict and why.
- The current version is the newest kept one; version 1 is seeded kept. A version is under test while its round is open with no verdict.
- `create_dispatch` and `create_evaluation` record the current version; `create_round_evaluation` records the version its round is evaluating.
- `get_version` and `get_current_version` return number, instructions, model and reasoning effort, and no scores.
- A version's scores are the averages, on each set, of the finished whole-set evaluations its rounds ran. Scoreboard evaluations and stopped evaluations don't count.

### Settings

| Setting | Starts at | Kept as |
| --- | --- | --- |
| Approval limit | $1,000.00, from `data/company.json` | dollars, above zero |
| Objectives on the held-out set | accuracy 0.6, grade 1.0 | accuracy 0 to 1, grade 0 to 3 |
| Noise | accuracy 0.1, grade 0.15, cost per claim 0.15, time per claim 0.15 | zero or more |
| Tolerance | accuracy 0.1, grade 0.15, cost per claim 1.0, time per claim 0.25 | zero or more |
| Spending limit for each round | $0.50 | dollars, above zero |
| Claim agents at once in the improver's evaluations | 25 | 1 to `MAX_AGENTS` |

Every change is a new row with who made it and when. A round keeps the row it started with. A new approval limit applies to decisions recorded after it. The page also lists the models allowed with their reasoning efforts and prices, read only, and the appearance, which each browser keeps.

### The judge

- State `{"handler": {decision, reason, reference}, "agent": {decision, reason, section}}`, with the lab's questions naming `agent.reason` and `agent.section`. The grade is Jev's `score`; the letter is the level with the highest probability, never the score rounded; the two checks kept as probabilities and shown as yes from 0.5.
- `server_url` passed on each call, `timeout_ms=10_000`, the SDK's retries off. Any error leaves the claim not graded and is logged.
- `finish_run` grades an evaluation in parallel, one thread per claim. From our swarm's lesson about threads and connections, it reads what it needs, lets go of its database connection, calls the judge, then records the grades in a new transaction, so 25 grading calls never hold one of the 4 connections for 10 seconds. Finishing stays under 20 seconds, within the agent's 30.
- An undecided claim gets F, score 0, both checks 0, without a call. A stopped evaluation isn't graded. With `MODEL_NAME` set, nothing is graded.
- An evaluation's grade averages its graded claims; with none it has no grade. Its judge cost is kept apart from the claim agents' cost.

### How a round works

The lab's loop, with the records in the backend:

1. A senior handler presses Start a round. The backend refuses while one is open, then asks the service, passing on its refusal.
2. The service takes the one-run lock or refuses, naming what holds it ("A dispatch is running", "Round 2 is running"). It creates the round, which records the handler, the settings row, the recipe, the current version, the improver's model, a new thread id and which first evaluations the version still needs: one on the evaluation set and two on the held-out set, less those it has.
3. The service runs those evaluations through the dispatcher, checking the round after each, then the improver until it pauses for a handler or ends.
4. `propose_change` with an allowed model pauses in `HumanInTheLoopMiddleware`. The service records the proposal and lets go of the lock; dispatches and evaluations can run while the round waits.
5. The Improvement page shows the proposal as a diff, with the model and reasoning effort before and after, and the reason. A senior handler approves after a confirmation, or rejects with a reason. The page names the proposal it shows, so a review never lands on another.
6. The backend passes the review to the service, which takes the lock (or refuses and records nothing), records the review, and resumes the improver. A rejection reaches the improver as the tool's answer with the reason. An approval makes the proposal a version under test.
7. `run_evaluation` asks for the version's evaluations, once on the evaluation set and twice on the held-out set; the backend refuses the first if the three could cost more than what's left. Then `record_verdict`: the backend keeps or rolls back the version by the rule and returns the verdict and scores.
8. `propose_recipe` pauses the same way; an approval makes it the current recipe.
9. When the improver ends, the service finishes the round. A version under test it never evaluated is rolled back; a round with no proposal finishes with no version tried.

A proposal outside the models allowed never reaches a handler: the middleware's `when` predicate lets the call through and the tool answers that it isn't allowed, recording nothing. The tool, the predicate and `create_version` share one check.

The round's stage is worked out by the backend from its records: `first_evaluations` (1, 2 or 3 of 3), `improving`, `change_waiting`, `evaluating` (1, 2 or 3 of 3), `verdict`, `recipe_waiting`, then `finished` or `stopped`.

### The rule

As the lab's `keep_or_roll_back`, with the round's settings: the new version's scores are the average of its two held-out runs, and the old ones the current version's held-out scores. Rolled back when its evaluations were stopped, when the round couldn't afford them, when it has no grade, or when it missed an objective; then when any measure got worse by more than its tolerance or none improved by more than its noise. Accuracy and the grade compare as differences, cost and time as fractions of the old value. The reasons use the lab's words, such as "accuracy improved" or "no score improved by more than the noise".

### Spending

A round's spending is its improver's calls, every model call in its evaluations, the first ones included, and the judge's. An evaluation's estimate is its claims times the highest cost per claim of any finished run on its model; for a model with no runs, the current model's times the larger ratio of their input and output prices. Once a round has spent its limit, `start_claim` refuses its copies, and `finish_run` marks the evaluation stopped. When the limit cuts short a first evaluation, the round stops before the improver runs.

### Stopping, restarts and one thing at a time

- Stopping a round marks it stopped, rolls back a version under test, and from then on the backend refuses anything the round records. The improver checks the round before each model call (`before_model`) and ends its stretch; the service lets go of the lock when the work in hand ends.
- On start the service marks running runs stopped, as today, and every open round not waiting for a handler. A round waiting for a handler survives a restart: its proposal is in the backend and the improver's progress is in its own `PostgresSaver` on the round's thread, `durability="sync"`.
- A stretch that fails stops the round with the error as the reason.

### The improver

- `create_agent` on GPT-6 Luna at `medium` (or `MODEL_NAME` at `default`), `context_schema` with the round and the evaluation function, read by the tools through `ToolRuntime`.
- The lab's four tools with the lab's names: `read_results` (`get_improver_view` as JSON), `propose_change`, `run_evaluation`, `propose_recipe`.
- Middleware: `HumanInTheLoopMiddleware` on the two propose tools (approve, reject), with the `when` predicate; `ModelCallLimitMiddleware(thread_limit=20, exit_behavior="error")`; a `wrap_model_call` that sets `parallel_tool_calls=False`; `after_model` recording each call's tokens and cost with the round; `before_model` ending a stopped round's stretch.
- Its instructions (`backend/instructions/improver.md`) are goals around the recipe: do better on claims it hasn't seen, within the objectives and the spending limit; what the claim agent works from (its instructions with the policy wording and the claims manual, the claim, the policy, the customer's earlier claims, and its tools for searching, reading sections and working out a payout); a change never names a claim; nothing takes effect until a handler approves it. The recipe is data, so it may be steps.
- What it sees (`get_improver_view`): the current version and its scores on both sets; from its latest round evaluation on the evaluation set, the wrong claims and the five right ones with the lowest grades, with the handler's decision, payout, reason and reference beside the agent's and the judge's grade and two checks; the earlier rounds; the objectives, noise, tolerance and rule; what's left of the spending limit; the models allowed. From the held-out set, scores only.

### API

Every operation keeps an `operation_id`, a one-line docstring and no optional inputs, and goes in the Postman collection.

| Router | Operation | Route | Who |
| --- | --- | --- | --- |
| `handlers` | `get_signed_in_handler` | `GET /api/me` | Signed in |
| `reviews` | `review_payout`, `decide_as_handler` | as today, without `handler_id` | Senior (over the limit) |
| `runs` | `start_dispatch`, `stop_run` | as today | Signed in |
| `evaluations` | `start_evaluation` | as today, without the model | Signed in |
| `runs`, `evaluations` | `create_dispatch`, `create_evaluation` | as today, without the model | |
| `evaluations` | `create_round_evaluation` | `POST /api/runs/rounds/{round_id}/evaluations` | |
| `configuration` | `get_current_version`, `get_version` | `GET /api/versions/current`, `/api/versions/{number}` | |
| `configuration` | `get_configuration`, `get_version_details` | `GET /api/configuration`, `/api/configuration/versions/{number}` | |
| `platform_settings` | `get_settings`, `change_settings` | `GET`, `PUT /api/settings` | change: Senior |
| `improvement` | `get_improvement`, `get_recipe` | `GET /api/improvement`, `/api/improvement/recipes/{number}` | |
| `improvement` | `start_round`, `stop_round` | `POST /api/improvement/rounds`, `.../{round_id}/stop` | Senior |
| `improvement` | `approve_proposal`, `reject_proposal` | `POST .../rounds/{round_id}/proposals/{proposal_id}/approval`, `/rejection` | Senior |
| `rounds` | `create_round`, `get_round`, `get_improver_view`, `record_change_proposal`, `record_recipe_proposal`, `record_review`, `create_version`, `create_recipe`, `record_verdict`, `record_improver_call`, `finish_round`, `stop_rounds` | under `/api/rounds` | the service |

`get_instructions` and `list_models` go. The agent's service gains `start_round` and `review_proposal`, each 202 or 409 naming what is running.

### Dashboard

Every page: a `PageHeader` with the title, a line on what the page is for and its main action; panels on an 8-pixel scale; numbers right-aligned with their units in JetBrains Mono with tabular figures; statuses as a chip with a color and a word; loading, empty and error states that say what to do next; `ConfirmDialog` before anything that changes the agent or a setting; nothing that moves as a page refreshes. Header: UnderCover, then Queue, Insights, Scoreboard, Improvement, Configuration and Settings, the current page marked, and the handler with Sign out. Dark mode from `data-theme` as well as `prefers-color-scheme`. All of it to `docs/BRAND.md`, at laptop sizes.

### End-to-end tests

- `e2e/auth-stand-in.ts` (new): an EC P-256 key pair made at start, the password grant for the three handlers, its public key at `/auth/v1/.well-known/jwks.json`, `/auth/v1/user`, `/auth/v1/logout`, and CORS. `node:crypto` only.
- `e2e/judge-stand-in.ts` (new): a fixed answer at `/api/alpha/decisions`: score 2.2 with B most likely, checks 0.8 and 0.3, cost $0.00002.
- The agent's stand-in also records round starts and reviews.
- A setup project signs in as Dana and as Marcus and keeps each browser's storage in `e2e/.auth/` (git-ignored).

### Following the lab, and where we differ from Ed

As in the lab: the rubric, the three questions in one call, the score as the grade and the most likely level as the letter; a configuration of instructions, model and reasoning effort, every change a new version; `difflib.unified_diff`; `compare` and `keep_or_roll_back` with its objectives, noise and tolerance; one evaluation-set run and two held-out runs per version; `create_agent` with `HumanInTheLoopMiddleware` on Luna at medium; the four tools with their names; the first recipe; the starting settings and the models allowed; the improver's view. Where the brief differs, we follow the brief, as Ed's plan lists.

Where we differ from Ed:

- We keep the handler's rejection, now a senior action, and the graceful Stop of a dispatch, now for a signed-in handler.
- `finish_run` releases its database connection before grading, from the swarm's thread and connection stall.
- `bench/` and the model picker go, because the configuration fixes the model.
- The Langfuse checks use `GET /api/public/v2/observations`, since the v1 traces list answers 410 and is removed on 2026-11-16. Ed's plan checks with `trace.list`.
- Our module split: routers per resource, SQL in `backend/store/`, and the round's work in `agent/rounds.py`.
- The Postman collection covers every new operation.

### Checked against the code standards

- One way to each service, each address once: `agent/connection.py` for the backend (both clients), `backend/judge.py` for the judge, `backend/auth.py` and `dashboard/src/auth.ts` for Supabase, `backend/agent_service.py` for the service, `e2e/stand-in.ts` for the stand-ins. `JUDGE_URL` and `VITE_SUPABASE_URL` in the env files only (rule 22).
- Modules keep to their jobs: `version_scores.py`, `spending.py` and `diffs.py` for what several routers need; the improver reaches claim agents only through the function the service hands it.
- Literals once: Jev's id and the rubric in `judge.py`; stages, statuses and verdicts as `StrEnum`s in the models; `default` for no reasoning effort; the improver's 20 calls in `improver.py`.
- The framework's own way: `HTTPBearer` and dependencies; `PyJWKClient`; `create_agent` with `context_schema`, `HumanInTheLoopMiddleware`, `ModelCallLimitMiddleware` and its hooks; `PostgresSaver` and `Command(resume=...)`; `difflib`; the `openrouter` client's own timeout and retries; `supabase-js` sessions; React context; Playwright's `storageState`.
- Size: `db.py`, `service.py`, `harness.py` and `styles.css` are watched; `styles.css`, at 1,499 lines, is split by area in phase 7 if ESLint's limits don't apply to it.
- Instructions as goals (rule 14) for `improver.md`; the recipe is data.
- Rules 7, 10, 13, 15 and 22 are updated for the improver, its client, `connection.py`, `auth.ts` and `data/models.json`.

### How the criteria are checked

API calls against `npm run dev` on Supabase after `npm run seed`, with a handler's token from Supabase Auth's password grant and `HANDLER_PASSWORD`. Pages in the browser with the Playwright MCP server, signed in. Tables and Auth users with the Supabase MCP server. Tests never call a model, the judge or Supabase Auth, and need no network. Before phase 7 no criterion runs the claim agent or the improver on the real model: runs and rounds are played out through the API.

## Phase 1: Handlers sign in

`auth.py`, `SignedIn`, `senior`, the handlers' emails and permissions, `get_signed_in_handler`, and the signed-in handler on every handler action that exists today (`review_payout`, `decide_as_handler`, `start_dispatch`, `stop_run`, `start_evaluation`). The dashboard's move into `pages/` and `components/`, `auth.ts`, the handler context and guard, the sign-in page, the header, the token on every request, the sign-off and rejection as the signed-in handler. Vite's `envDir`. The Auth stand-in, the setup project, every e2e spec signed in. `PageHeader` and `NotAllowed` start here.

Built on 2026-10-28. `NotAllowed` starts here and `PageHeader` with the Configuration page in phase 2, its first user. `bench/` was retired in this phase rather than phase 2, since it started evaluations without signing in. A live check found that a token Supabase had just issued could read as issued in the future by this machine's clock, which PyJWT refuses, so `auth.py` allows the clocks 30 seconds; a test covers it. The review moved `SignedIn` and `senior` into `backend/signed_in.py`, which checks the token before taking a database connection and finds the handler on a short connection of its own, so `start_dispatch`, `stop_run` and `start_evaluation` hold none while they wait for the agent's service; the dashboard checks a handler once per user rather than per token, so an hourly refresh never blanks the page; `list_handlers` no longer returns emails. Showing a handler who can't approve over the limit why, in place of the button, on a referral comes with the Settings page in phase 3, when the dashboard reads the limit; the backend refuses it now.

- [x] `pyjwt[crypto]` in the product's dependencies and `@supabase/supabase-js` in `package.json`
- [x] pytest, with a key pair made in the test: Dana's token returns Dana Whitfield, Senior Claims Handler, her email and `can_approve_over_limit` true; no token, another key's token, an expired one and another audience each return 401; a valid token for an unknown email 403
- [x] pytest: one list of every handler operation, each 401 without a token and doing nothing; later phases add theirs
- [x] pytest: `review_payout` as Dana signs off and rejects a held payout, recording her; as Marcus it returns 403 "Only a handler who can sign off payouts over $1,000.00 can review this payout. Marcus Oyelaran can't." and changes nothing
- [x] pytest: `decide_as_handler` as Marcus approves a referred claim under the limit and is refused one over it
- [x] pytest: `start_dispatch`, `stop_run` and `start_evaluation` as Marcus reach the agent's service
- [x] pytest: after seeding, Dana is senior and Marcus and Priya aren't, each with their email
- [x] `VITE_SUPABASE_URL` and `jwks` appear in the backend only in `backend/auth.py` and its tests, and `supabase-js` in the dashboard only in `auth.ts`
- [x] vitest: a visitor goes from `#/scoreboard` to `#/sign-in` and back after signing in; a refused sign-in shows the refusal; the header shows the handler and Sign out signs out; every request carries the token
- [x] vitest: a held payout shows Sign off and Reject for Dana with no handler to choose, and for Marcus no buttons, with why
- [x] e2e: the setup project signs in as Dana and Marcus; every existing spec passes signed in; signing out lands on the sign-in page; Marcus sees why he can't review a held payout
- [x] Postman: the token on handler actions, from the Auth stand-in's or Supabase's password grant
- [x] Live: `POST /api/dispatches` with no token returns 401, and with Marcus's token and the agent's service stopped 503
- [x] Browser: sign in as Dana, see the queue with her name and role; a wrong password shows the alert; Sign out; screenshots in light and dark with no console errors
- [x] `npm run check` passes with `.env` moved out of the way

## Phase 2: The configuration in versions

`versions` and version 1, `data/models.json` and `models_allowed`, `free_model.py`, the four configuration operations, `diffs.py`, the version on every run, the claim agents built from the run's version, `connection.py`. `get_instructions`, `list_models`, `settings/models.toml`, `agent/config.py`, the model picker and `bench/` go. On the dashboard, the Configuration and version pages replace Instructions, with `DiffView`.

Built on 2026-10-28. `get_version` and `get_current_version` also give the model's provider and its build options (Luna's `max_tokens`), which the claim agent needs to build its model and which aren't scores; version 1's model is named in `data/models.json` (`first_version`), since no model id is written in code. `bench/` went in phase 1. The schema's shared parts moved to `backend/schema.py`, and a database missing any table is seeded afresh. Anthropic leaves the product: a model call's cost is what OpenRouter reports, or nothing for a local model. The student's `.env` line `MODEL_NAME=anthropic:claude-haiku-5-5` was commented out, as the decisions above said.

- [x] Seeding reports "and version 1 of the configuration"; version 1 is `claim.md`, `openai/gpt-6-luna`, `low`; with `MODEL_NAME=openrouter:openrouter/free` it is that model at `default`, the only model allowed, priced 0
- [x] pytest: `get_current_version` and `get_version` return exactly number, instructions, model and reasoning effort, with the model's provider and build options; an unknown version 404
- [x] pytest, `diffs.py`: one line changed gives one removed and one added line with two of context; two far apart give two hunks; the same text none
- [x] pytest: with version 2 kept and 3 under test (made by a test helper), the current version is 2, `get_configuration` lists 3, 2, 1 with their statuses and lines added and removed, and `get_version_details` for 3 has its diff from 2
- [x] pytest: `create_dispatch` and `create_evaluation` record the current version, shown by `get_latest_dispatch`, `list_evaluations` and `get_evaluation`
- [x] Stub model test, through the service: with version 2 current on another model, a dispatch's claim agents get version 2's instructions and model; the one-claim command and a resume after a sign-off use the current version
- [x] pytest: `default` builds a model with no reasoning effort, `medium` with medium; Luna gets `max_tokens` 16000 from `data/models.json`
- [x] `MODEL_NAME` is read only in `backend/free_model.py` and tests; `UNDERCOVER_API` only in `agent/connection.py`; nothing finds `get_instructions`, `list_models`, `models.toml` or `bench`
- [x] The test that `agent/api.py` can't read the scoreboard also covers the configuration's dashboard reads
- [x] vitest: the Configuration page shows the current version and the versions with status chips; a version's page shows a diff with added and removed lines marked; `#/instructions` lands on `#/configuration`; the forms no longer offer a model
- [x] e2e: the header's Configuration link shows version 1 as Current with its instructions
- [x] Postman, Supabase MCP: `versions` has one row, `models_allowed` three, `runs` has `version` and `round_id`
- [x] Browser: the Configuration page and version 1 in light and dark; a dispatch played out through the API shows version 1 on the dispatch panel
- [x] `npm run check` passes

## Phase 3: Settings

`platform_settings` as a history, `data/improvement.json`, `get_settings` and `change_settings`, the approval limit from the settings, the Settings page with `ConfirmDialog`, and the appearance.

- [ ] pytest: seeding makes row 1 from `company.json` and `improvement.json` with nobody as author, and the models allowed with numeric prices
- [ ] pytest: `change_settings` as Dana records row 2 with her and the time; as Marcus 403 with why and nothing recorded; without a token 401
- [ ] pytest: a limit of 0, an accuracy floor of 1.5, a grade floor of 4, a negative noise, a spending limit of 0 and 26 agents each 422
- [ ] pytest: with the limit raised to $1,500.00, a 1,350.00 approval recorded after is paid without sign-off and one recorded before still waits; lowered to $500.00, a 600.00 approval waits and `pay_claim` refuses it
- [ ] `payout_approval_limit` is read only by seeding, and no `1000` appears in the backend outside tests
- [ ] vitest: each setting with its unit and "Last changed by"; Save opens the dialog listing old and new values, Cancel sends nothing, Confirm sends them; a refusal shows; Marcus sees it read only with why; the models allowed right-aligned; the appearance sets `data-theme` and remembers it
- [ ] vitest: `ConfirmDialog` is a modal with a title, the changes and two buttons, closing on Cancel and Escape
- [ ] e2e: Dana sets the spending limit to $0.75, which stays after a reload; Marcus has no Save and is told why; Dark sets `data-theme="dark"` and stays after a reload, Light holds under a dark system setting
- [ ] Postman, Supabase MCP: one settings row and three models allowed after a seed
- [ ] Browser: raise the limit to $1,500.00 and approve `CLM-1004` for 1,350.00 through the API: paid without a sign-off. The page in light, dark and the computer's setting. `npm run seed` afterwards
- [ ] `npm run check` passes

## Phase 4: The judge

The handlers' reasons and references in seeding, `judge.py`, `grades`, grading in `finish_run`, the grade and the judge cost in the measures, the judge's stand-in, and the grade on the Scoreboard and an evaluation's page.

- [ ] pytest: seeding stores a reason and reference for all 50 decisions; nothing the claim agent's client reads holds either
- [ ] pytest, with an httpx `MockTransport`: the request goes to `JUDGE_URL` with Jev's id, the state and the three questions, with a 10 second timeout and no retries
- [ ] pytest: score 1.5 with probabilities 0.4, 0.05, 0.2, 0.35 for F, C, B, A gives F; the checks keep their probabilities and show yes from 0.5
- [ ] pytest: a judge that times out, answers 500 or answers without the grade leaves the claim not graded after one request, and the evaluation finishes
- [ ] pytest: 25 copies with a judge taking 0.3 s a call finish in under 2 s, and the grading holds no database connection while it waits (checked through the engine's checked-out count)
- [ ] pytest: an undecided copy is F without a call; the evaluation's grade leaves out an ungraded copy; with none graded it has no grade; the judge cost is apart from the model cost; a stopped evaluation isn't graded; with `MODEL_NAME` set, no call
- [ ] Jev's id, `JUDGE_URL` and the Decisions call appear only in `backend/judge.py` and its tests
- [ ] vitest, e2e: the Scoreboard shows the grade as 2.20 or "Not graded"; an evaluation's page shows each claim's chip, score and the two checks, with the judge cost
- [ ] Live, judge only: the lab's four explanations for CLM-1001 give the handler's reason B or A, CLM-1003's F, the vague one C or F and the clearer one A, for under $0.001
- [ ] Live, judge only: the held-out tiny claims played out through the API with one left undecided finish in under 20 s with four graded and one F, shown in light and dark. `npm run seed` afterwards
- [ ] Postman, `npm run check` passes

## Phase 5: The improver

In the backend: `recipes` and recipe 1, `rounds`, `proposals`, `improver_calls`, verdicts on versions, `version_scores.py`, `verdict.py`, `spending.py`, the `rounds` and `improvement` routers, `create_round_evaluation`, and the refusals for a stopped or spent round. In the agent: `improver_api.py`, `improver.py`, `rounds.py`, `start_round` and `review_proposal`, the lock that names what holds it, `stop_rounds` at start, the round's session and tags. Tested on a stub model with a script of tool calls and a stub judge.

- [ ] pytest, `verdict.py`, against an old version at 0.60, 1.50, $0.0010 and 20 s with the lab's noise and tolerance: 0.72, 1.50, $0.0019, 24 s kept, "accuracy improved"; $0.0021 rolled back, "cost_per_claim got worse"; 0.60, 1.50, $0.0008, 20 s kept, "cost_per_claim improved"; 0.68, 1.60 rolled back, "no score improved by more than the noise"; grade 0.90 rolled back, "it missed the objectives on grade"; no grade rolled back
- [ ] pytest: a version's scores average only its rounds' finished whole-set evaluations, leaving out a Scoreboard one and a stopped one
- [ ] pytest: `get_improver_view` holds what the brief lists, and no held-out claim id, summary or reason
- [ ] pytest: a recorded proposal changes nothing until approved; after approval `create_version` makes version 2 under test, proposed by "Round 1", approved by Dana, version 1 still current; a repeat returns it; a model outside the models allowed 422; `record_review` refuses Marcus
- [ ] pytest: reviewing a proposal that isn't the one waiting 409, another round's 404, asking nothing of the service
- [ ] pytest: `start_round`, `stop_round`, `approve_proposal` and `reject_proposal` are in the handler list and refuse Marcus with why; `create_round` refuses while one is open
- [ ] pytest, spending: with Luna's highest cost per claim at $0.002, $0.10 left refuses the evaluations, "about $0.15, and $0.10 of the round's limit is left", and the verdict rolls back, "the round couldn't afford to evaluate it"; a Gemini version with no runs is estimated at 5 times Luna's; a spent limit refuses the next copy's start and stops the evaluation
- [ ] pytest: a round keeps its settings row after a change; stopping with a version under test leaves version 1 current and refuses the round's later records; stopped after its verdict keeps the version
- [ ] pytest: `get_improvement` gives each stage at the point a round reaches it, with "2 of 3"
- [ ] Stub model test, through the service: on a fresh database a round runs its three first evaluations and the improver proposes; the round waits at `change_waiting` with the lock free
- [ ] Stub model test: a rejection's reason reaches the improver, which proposes again; an approval makes version 2, evaluated once and twice at the round's agents at once, and kept; the recipe approved; the round's cost is the improver's calls, the evaluations' model calls and the judge
- [ ] Stub model test: a proposal of `openai/gpt-7` goes back with "isn't allowed" and records nothing
- [ ] Stub model test: an approval while a dispatch runs is 409 "A dispatch is running", recording nothing; a round start while an evaluation runs is refused; a dispatch while a round waits starts
- [ ] Stub model test: a waiting round survives the service's lifespan running again and resumes from its saved progress on approval; one in its first evaluations is stopped
- [ ] Stub model test: stopping during evaluations starts no more claims or model calls and frees the lock; the improver stops after 20 calls across an approval; a round with no proposal finishes with none tried; a spending limit spent by the first evaluation stops the round before the improver runs
- [ ] Stub model test: the round's evaluation claims are tagged with the run and the round, and each stretch is traced in the round's session
- [ ] A test checks that `agent/api.py` has nothing under `/api/rounds`, `/api/improvement`, `/api/configuration` or `/api/settings`, nor the evaluation reads; that `tools`, `graph` and `harness` don't import `improver_api`; and that `improver` imports neither `harness` nor `dispatcher`
- [ ] Postman: every new operation
- [ ] Live, through the API: a round created by the service's operations shows at `first_evaluations`; `start_round` as Dana is 409 while it's open; `stop_rounds` stops it; with the service stopped, approving a recorded proposal is 503 and a made-up one 404. `npm run seed` afterwards
- [ ] `npm run check` passes

## Phase 6: The Improvement page

The Improvement page and a recipe's page, with `RoundProgress`, `VersionChart`, `DiffView` and `ConfirmDialog`, and round starts and reviews through the agent's stand-in.

- [ ] vitest: no rounds says "No rounds yet." with what Start a round does; Start posts once and shows a refusal; Stop shows while a round is open
- [ ] vitest: each stage shows where the round has got to, with "First evaluations, 2 of 3"; a finished round its verdict and why; a stopped one who or what stopped it
- [ ] vitest: a waiting change shows its diff, model and effort before and after, and the reason; Approve confirms then posts to the proposal shown; Reject needs a reason; a 409 shows in an alert; a waiting recipe uses the same `DiffView`
- [ ] vitest: Marcus sees no Approve, Reject or Start, with why
- [ ] vitest: the rounds table, right-aligned, with scores before and after, verdict, who reviewed what and when, and cost against the limit; the chart one point per version tried in each of two charts, colored by verdict, with version 1's line and labelled axes
- [ ] e2e: a round played out through the API to a waiting change shows its diff; Dana's approval, confirmed, reaches the stand-in with the round, the proposal and Dana; once the test records the review and version as the service would, the page moves to "Evaluations, 0 of 3" without a reload
- [ ] e2e: rejecting a recipe with a reason reaches the stand-in with it; Marcus sees no buttons
- [ ] Browser: a round played out to a waiting change, in light and dark at 1280 by 800 and 1440 by 900, the diff readable and no console errors. `npm run seed` afterwards
- [ ] `npm run check` passes

## Phase 7: The whole dashboard, the live runs and the docs

Bring every existing page to the standard of the new ones, changing nothing about how it works. Then the live checks the brief asks for, after one `npm run seed`, on the default model, with `MODEL_NAME` out of `.env`. Estimated spend: three first evaluations and three for each of two versions tried, 225 claims at about $0.001 each with the judge, the improver's calls and a dispatch at N=25, about $0.40, well inside the $3.88 left on the key.

- [ ] vitest: every page has a `PageHeader` with a title and its purpose; every numeric column is right-aligned; every loading, empty and error state uses `StateMessage` and says what to do
- [ ] Browser, `browser_evaluate`: a `PerformanceObserver` records no layout shift over three refreshes on the queue, a claim in progress, the Scoreboard, an evaluation and the Improvement page; every button has the same height, radius and font; titles, panels and first columns line up at 1280 by 800
- [ ] Live: signed in as Dana, round 1 from the Improvement page shows its first evaluations as they happen; the first proposal is rejected with a reason, the next approved; its evaluations, verdict and recipe proposal show as they happen; the recipe is approved and the round finishes
- [ ] Live: round 2 on recipe 2, with its change and recipe approved, finishes
- [ ] Live: the rounds show held-out scores before and after, the verdict, who approved or rejected what and when, and the cost; the Configuration page shows the versions with diffs and held-out scores; the recipe's versions have diffs
- [ ] Live: each round's improver traces are found in one Langfuse session through `GET /api/public/v2/observations`, and its evaluations' claims by the round's tag
- [ ] Live: report how far version 1's two held-out runs differed on each measure, beside the noise and the tolerance. Time per claim at N=25 waits on database connections (about 60 s a claim in our swarm's runs, against 6 s in the lab), so its noise may decide verdicts; report it
- [ ] Live: a dispatch at N=25 on the current version finishes; Marcus can't sign off a held payout or change the settings, each saying why; Dana signs it off and it shows paid within five seconds
- [ ] Live: report what the checks spent, from the backend's records and the key's usage; under $1
- [ ] Screenshots of every page in light and dark at 1440 by 900. A fresh subagent reviews them once as a senior product designer against `docs/BRAND.md` and point 8 of the brief; every finding is fixed or answered in the report, and fixed pages are shot again
- [ ] `docs/SPEC.md` (the approval limit as a setting, the improver reading the evaluation set's handlers' decisions and reasons while the claim agent never sees them and nothing in the agent reads the held-out set's, sign-in, the improver, what the team sees), `docs/TECH_STACK.md`, `docs/PROCESS.md` (signing in for browser checks, the stand-ins, these live runs), `docs/CODE_STANDARDS.md` (7, 10, 13, 15, 22), `data/README.md` (emails, who is senior, `improvement.json`, `models.json`, `MODEL_NAME` before seeding), `docs/STATUS.md`, `CLAUDE.md` and the README describe the product as it now is
- [ ] `npm run check` passes with `.env` in place and moved out of the way

## Not in this plan

- Signing in for the agent's service, until Week 3 brings an API key.
- Editing a proposal before approving it.
- Sending the judge's grades to Langfuse as scores.
- Clearing old checkpoints, copies and rounds; a reseed clears them.
- Running rounds on free models; students on them build and test everything.
- The short policy wording as a fourth lever.
- Real payments, messages to customers and sign-up.
