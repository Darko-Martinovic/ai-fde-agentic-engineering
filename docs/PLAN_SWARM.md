# Plan: a swarm of claim agents and a scoreboard

This plan builds what `docs/SWARM.md` asks for (a copy of `labs/week2day4_product_SWARM.md`, as Ed's `week2day4-start` adds it, committed with this plan) on top of our durable-state build, in six phases. Each phase leaves `npm run check` green, is reviewed by a fresh subagent and goes in through its own PR on the fork before the next one starts.

SIDENOTE: For consistency with the course, please read `labs/week2day4.ipynb` and build the dispatcher in the same style as the lab. Where the lab and this brief differ, follow the brief. Include this sidenote in your plan too.

When it's done, a handler starts a dispatch from the queue page with N claim agents at once, 3 to start with. A dispatcher with no model, a LangGraph graph like the lab's, carries on every claim left in progress and works every waiting claim, oldest submitted first, each on its own thread with its saved progress, its pause for a handler's review and its recovery after a restart. A rate limit or a timeout waits and carries on; any other failure gets one more try in the same dispatch. Every model call's tokens and cost and every spell of work on a claim are recorded with their run. A Scoreboard page starts evaluations on copies of the labelled claims and scores them with the lab's measures. The queue agent and its to-do list are gone, and the agent runs on GPT-6 Luna at low reasoning by default.

Ed's `upstream/week2day4-end` was read before this plan was written. His build starts from his durable-state build, which differs from ours (one `main.py`, no Run and Stop on the dashboard, no rejection), so this plan follows his design where it fits our code and says where it differs.

## Decisions for the student

The student confirmed each of these on 2026-10-27.

| | Recommended | Why |
|---|---|---|
| Stop on the dashboard | Keep a Stop button, as a graceful stop: the dispatch starts no more claims, the claims already working finish their current spell, and the run shows as stopped | We have Stop today. The service works a dispatch in threads, which can't be killed one by one, and a hard stop is what a restart already tests |
| The model picker | Keep it: the dispatch and evaluation forms offer the models in `settings/models.toml`, with `MODEL_NAME` (GPT-6 Luna by default) chosen | We have it today, and the scoreboard is most useful when an evaluation can be run on another model without editing `.env` |
| Cost | OpenRouter's `usage.cost` when the reply carries it, as the brief asks; otherwise the prices in `settings/models.toml`, as today, for Anthropic and Ollama | The brief's source of cost exists only on OpenRouter |
| Run and Carry on on a claim's page | Remove them: claims are worked by dispatches, and `uv run -m agent CLM-1001` still works one | A run of one claim beside a dispatch would need its own place in "one run at a time" |
| The model comparison (`bench/`) | Rebuild it on evaluations in phase 5: each trial starts an evaluation through the backend and reads its measures, so `bench/score.py` and its reading of `data/evals/` go | Two scorers of the same answer key would drift apart; the backend's seeding becomes the one reader |
| Connections | 4 a process, as the brief allows (3 today) | 25 claim agents share them; if the pooler fills in the live runs, go back to 3 |

## Design

### What changes, in one picture

```
dashboard ──/api──> backend ──> Supabase (records, model calls, work times, runs, answer key)
                      │ start_dispatch / start_evaluation / stop_run / resume_claim
                      v
                  agent's service ── dispatcher (LangGraph, no model, max_concurrency=N)
                                         │ Send per claim
                                         v
                                  harness.work_in_run ── claim graph, own thread, own PostgresSaver
                                                                 on the service's pool of 4
```

### Modules

The backend:

- `db.py`: the tables gain `model_calls`, `work_times`, `run_claims`, `held_out_claims` and `handler_decisions`; `runs` is reworked for dispatches and evaluations; `claims` gains `evaluation_id` and `copy_of`; `todos` and `usage` go (usage becomes `model_calls`). Seeding drops the old tables first when they exist, before `runs`.
- `seed.py`: also reads `data/evals/decisions.json`, `held_out_claims.json` and `held_out_decisions.json`, into `held_out_claims` and `handler_decisions`. It becomes the only reader of `data/evals/`; `tests/test_standards.py` checks that.
- `store/runs.py`: runs, their claims, their summaries and their totals. `store/usage.py` (new): model calls and work times. `store/evaluations.py` (new): copies and the answer key, the only module that reads `handler_decisions`.
- `scoring.py` (new): the lab's measures as plain functions, `WRONGFUL_DECLINE = 1500` and `NEEDLESS_REFERRAL = 50`, like `payout.py`.
- `runs.py`: the operations on runs the agent's service writes (`create_dispatch`, `create_evaluation`, `record_run_claims`, `finish_run`, `stop_runs`), and the ones the dashboard reads (`get_latest_dispatch`, `list_evaluations`, `get_evaluation`), and the starts it asks the service for (`start_dispatch`, `start_evaluation`, `stop_run`).
- `usage.py` (new router): `record_model_call` and `record_work_time`, which belong to a claim.
- `agent_service.py`: the backend's calls to the service: `resume_claim`, `start_dispatch`, `start_evaluation` and `stop_run`, with the address written once and "The agent's service isn't running" for a 503.
- `runner.py` goes: the backend no longer starts processes. `list_models` moves to a small `models.py` router reading `settings/models.toml` through `agent.config`, as today.
- `reviews.py`: `review_payout` refuses an evaluation's copy (409), for a sign-off and a rejection alike.
- `claims.py` and `insights.py`: leave out evaluations' copies, so the queue and Insights are as they were.

The agent, in five parts (`docs/CODE_STANDARDS.md` 13):

- `api.py`: gains the operations above that the service and the harness use, and loses `start_run`, `write_todos`, `get_latest_run` and `record_usage`. No function for `list_evaluations` or `get_evaluation`, so the agent never reads the handlers' decisions (a test checks it). Its client retries a refused connection a few times (httpx's `HTTPTransport(retries=5)`), since `npm run dev` starts the backend and the service at once.
- `harness.py`: `work_claim` and `carry_on` as today, with the run's id or none; the new `work_in_run(claim_id, run_id, new_graph)`, the one function the dispatcher calls, which carries on a claim in progress or starts a waiting one and returns its report line; `TRANSIENT = (ModelRateLimitError, ModelTimeoutError)`, which it lets through without settling the claim. It times each spell of work with `time.monotonic()` and records it, so a pause for a review ends a spell and the wait is never counted. A held copy's thread is cleared with `delete_thread`. `finish_stopped_run` and `carry_on_stopped` go: the next dispatch does their work.
- `reports.py` (new, phase 1): the line each piece of work on a claim reports, moved from the harness to keep it under 300 lines.
- `dispatcher.py` (new): the dispatcher graph, its state and context, and `work_run(run, work, skip)`.
- `graph.py`: the `agent` node records each reply's tokens and cost with `record_model_call` (OpenRouter's `token_usage.cost`, or the model's prices). Nothing else in the graph changes.
- `checkpoints.py`: `pool()` opens the process's `ConnectionPool` (at most `DATABASE_CONNECTIONS`, `timeout=120`), makes the schema and runs `setup()` once; `new_saver(pool)` gives each claim run a `PostgresSaver` of its own, since one saver holds a lock around every read and write.
- `service.py`: `health` and `resume_claim` as today, and `start_dispatch`, `start_evaluation` and `stop_run`. One run at a time, a lock a start takes without waiting. Its lifespan opens the pool and marks any run still running as stopped. It keeps the claims it is resuming after a review in a set that a dispatch skips.
- `queue_agent.py`, `middleware.py`, `backend/instructions/queue.md` and the queue tools go. `__main__.py` keeps `uv run -m agent CLM-1001`, with no run; `--cap` and the queue go.
- `tracing.py`: each claim's trace worked in a run gets `langfuse_tags: ["run-7"]`, its run's id, the same for a dispatch and an evaluation; the `run-queue` trace goes.

Dependencies inside the agent: `service` uses `dispatcher`, `harness` and `api`; `dispatcher` uses `harness` and `api`; `harness` uses `graph`, `checkpoints`, `tools`, `tracing` and `api`. The dispatcher reaches the claim agent only through `harness.work_in_run`.

The dashboard: the run panel becomes the dispatch panel, the agent bar becomes the dispatch form (N from 1 to 25, 3 chosen, the model, Start and Stop), and there is a new Scoreboard page and an evaluation page. The to-do list, the claim page's Run and Carry on, and the queue instructions go.

### The dispatcher

As in the lab: a `TypedDict` state with `operator.add` on the results, a `list_claims` node, `fan_out` returning one `Send("work_claim", claim_id)` per claim, a `work_claim` node with a `RetryPolicy`, `max_concurrency` set to N, no model, and a `finish_run` node that LangGraph runs once after every `work_claim`, as in our Week 2 Day 4 challenge.

| From | To | How |
|---|---|---|
| START | `list_claims` | always |
| `list_claims` | `work_claim` | `fan_out`: one `Send` per claim |
| `list_claims` | `finish_run` | `fan_out`, when there are no claims |
| `work_claim` | `finish_run` | always |
| `finish_run` | END | always |

- `list_claims`: for a dispatch, the queue's claims in progress, then waiting, oldest submitted first, less those the service is resuming, recorded with `record_run_claims`. For an evaluation, its copies.
- `work_claim`: if the run has been asked to stop, it starts nothing and reports the claim as left for the next dispatch. Otherwise it calls `work_in_run`. A claim back in the queue after a failure is worked once more, as a new attempt; a second failure leaves it for a handler, as today.
- `finish_run`: finishes the run, or marks it stopped when Stop was asked; the backend builds a dispatch's summary from its records.
- The dispatcher has no checkpointer: each claim saves its own progress, and the next dispatch finishes what a stopped one left. Each claim graph runs in a fresh `contextvars.Context`, as our harness does today for Langfuse, which also keeps LangGraph from treating it as a subgraph of the dispatcher: its checkpoints stay under the claim's thread with no namespace, and its `interrupt()` pauses that claim and not the dispatch. A test checks both, since our Week 2 Day 4 challenge showed that a graph invoked inside a node is otherwise saved under the node's namespace.
- Retries: `RetryPolicy(max_attempts=3, initial_interval=10, retry_on=harness.TRANSIENT)`. The brief has the worker's `error_handler` leave a claim in progress when the retries run out. Ed found that LangGraph 1.2.12 re-raises a handled error from `invoke` when workers fail side by side. Phase 2 first checks that with a test; if it holds, `work_claim` catches the error on its last try (from `runtime.execution_info.node_attempt`) and reports the claim as left for the next dispatch, as Ed does, and the test keeps watch for a LangGraph release that fixes it. The tests take the waits out of the policy with a fixture.

### Runs

| Field | Meaning |
|---|---|
| `run_id` | A number, shown as `#7`, and part of a copy's id |
| `kind` | `dispatch` or `evaluation` |
| `agents` | N, from 1 to 25 |
| `model`, `reasoning_effort` | The model's spec and its reasoning effort from `settings/models.toml`, or `none` |
| `evaluation_set`, `tiny` | For an evaluation: `evaluation` or `held_out`, and whether it's the five `tiny` claims |
| `status` | `running`, `finished` or `stopped` |
| `started_at`, `finished_at`, `summary` | `summary` is a dispatch's, built from the records when it finishes |

The summary: `{approved, declined, referred, waiting_for_sign_off: [{claim_id, payout}], left_for_handler: [...], unfinished: [...]}`, each claim counted once. A dispatch's claims show their queue line, and their model cost, seconds and start in this run.

### Cost and time

- `model_calls`: the claim, its thread, the run or none, the model, input and output tokens, cost and time.
- `work_times`: the claim, its thread, the run or none, the start and the seconds.
- A run's totals are its rows, failed attempts and retries included. A carry-on after a review is recorded with no run, so a run's totals are its own.

### Evaluations and the scoreboard

- `create_evaluation` makes the run and a copy of each claim of its set (25, or the five `tiny`), waiting, with `evaluation_id` and `copy_of`, id `CLM-1104-E7` written into its record too. Copies work through every claim operation; `list_claims`, Insights and a dispatch leave them out.
- Nobody can review a copy: `review_payout` refuses it with a 409, and its page has no review form. An approval held for sign-off counts as finished, and `work_in_run` clears its thread.
- The backend scores an evaluation when it's read: `decision_accuracy`, `accuracy`, `cost_of_mistakes`, `straight_through`, `model_cost_per_claim`, `seconds_per_claim` and `run_seconds`, with a claim the agent didn't decide counted as a referral.
- `get_claim` on a copy, and every response the agent can read, holds nothing from `handler_decisions`.

### API

Every operation keeps an `operation_id`, a one-line docstring and no optional inputs; new and changed ones go into the Postman collection.

| Operation | Route | What it does |
|---|---|---|
| `record_model_call` | `POST /api/claims/{claim_id}/model-calls` | `{thread_id, run_id, model, input_tokens, output_tokens, cost, seconds}` |
| `record_work_time` | `POST /api/claims/{claim_id}/work-times` | `{thread_id, run_id, seconds}` |
| `start_dispatch` | `POST /api/dispatches` | `{agents, model}`; asks the service; 202, or its 409, or 503 |
| `start_evaluation` | `POST /api/evaluations` | `{evaluation_set, tiny, agents, model}`; the same |
| `stop_run` | `POST /api/runs/stop-request` | Asks the service to stop the running run; 202, or 409 when none runs |
| `get_latest_dispatch` | `GET /api/dispatches/latest` | The newest dispatch with its claims, cost, time and summary, or null |
| `list_evaluations` | `GET /api/evaluations` | Every evaluation, newest first, with its measures |
| `get_evaluation` | `GET /api/evaluations/{run_id}` | One evaluation, its claims beside the handlers' decisions |
| `create_dispatch`, `create_evaluation` | `POST /api/runs/dispatches`, `/api/runs/evaluations` | Record a new run, running (the service only) |
| `record_run_claims` | `PUT /api/runs/{run_id}/claims` | A dispatch's claims, in order |
| `finish_run` | `POST /api/runs/{run_id}/finish` | `{stopped}`; finishes or stops a run, with a dispatch's summary |
| `stop_runs` | `POST /api/runs/stop` | Marks every running run stopped (the service, as it starts) |
| `get_instructions` | `GET /api/instructions` | The claim instructions alone |

`start_run`, `write_todos`, `get_latest_run`, `record_usage`, `get_agent`, `run_claim`, `run_queue` and `stop_agent` go.

### Following the lab, and where we differ from Ed

As in the lab: the graph's shape, `Send`, `max_concurrency`, `RetryPolicy`, a node after the workers, no model in the dispatcher, the lab's measures, GPT-6 Luna at low reasoning, cost from `usage.cost`, the `tiny` subsets. Where the brief differs, we follow the brief: each claim keeps its own thread and saver; only transient errors are retried, and a retry carries the claim on; the records live in the backend; Langfuse tags each claim's trace rather than one trace for the run; scores aren't sent to Langfuse.

Where we differ from Ed's build: a graceful Stop and a model picker on the dashboard; cost from `settings/models.toml` where the provider reports none; a handler's rejection, refused on a copy like a sign-off; our module split (`store/`, routers per resource); and `bench/` rebuilt on evaluations.

### Checked against the code standards

- One way to call each service, each address written once: the agent to the backend through `api.py`, the dashboard through `api.ts`, the backend to the service through `agent_service.py`, the e2e tests to the stand-in through its own module.
- Modules keep to their jobs: the dispatcher chooses and tracks, and reaches the claim agent only through `work_in_run`; scoring apart from routes; seeding the only reader of `data/evals/`; `store/evaluations.py` the only reader of `handler_decisions`.
- Literals once: `TRANSIENT`; the most agents at once, 25, in `settings/.env.defaults` (`MAX_AGENTS`) for every part; the measures' constants in `scoring.py`.
- Functions under 40 lines, modules under 300: `runs.py` and `harness.py` are watched; the summary and the copies get their own store functions.

## Phase 1: GPT-6 Luna by default, and cost and time

Add GPT-6 Luna to `settings/models.toml` (reasoning `low`, $0.10 and $0.50 a million tokens) and make it `MODEL_NAME` in `settings/.env.defaults`. Add `model_calls` and `work_times`, `record_model_call` and `record_work_time`, the run's id in `ClaimContext`, recording in the graph's `agent` node and the harness, and Langfuse tags. The queue run still exists, so its claims record its id.

- [x] pytest: with no `MODEL_NAME` override the model is `openai/gpt-6-luna` with `reasoning_effort="low"`; another model in `settings/models.toml` runs with its own options
- [x] pytest, backend: `record_model_call` and `record_work_time` record their rows with a run and with null; a claim not started returns 409, an unknown claim or run 404, negative numbers 422
- [x] Stub model test: a stub reply with `token_usage.cost` records that cost; a stub with no cost records the cost from the model's prices
- [x] Stub model test: `CLM-1001` worked with no run records one model call per reply and one spell of work, with no run
- [x] Stub model test: a claim whose first attempt fails after one model call, worked again in the same run, has both attempts' model calls and spells under the run
- [x] Stub model test: `CLM-1002` approved for 1,350.00 pauses; the clock moves on an hour; it is signed off and carried on. It has two spells, together under a second, the second with no run. The same for a rejection, whose carry-on makes its own model calls with no run
- [x] Stub model test: in a queue run of two claims, every model call and spell carries the run's id, and each claim's trace has the run's tag; `CLM-1001` alone has none
- [x] Postman: the two new operations, against the dev backend
- [x] `npm run check` passes

## Phase 2: The dispatcher in place of the queue agent

Add `dispatcher.py`, `work_in_run`, `TRANSIENT`, the pool with a saver per claim run, and the retry fixture. Rework `runs` and add `run_claims`, `create_dispatch`, `record_run_claims`, `finish_run` with its summary, `stop_runs` and `get_latest_dispatch`. Give the service `start_dispatch`, one run at a time, the stop at startup, the graceful stop and the claims it is resuming. Remove the queue agent, its middleware and instructions, the to-do list, `runner.py`, and the claim page's Run and Carry on. On the dashboard, the dispatch panel shows the latest dispatch, without the form yet.

- [ ] `grep -rn "create_agent\|Middleware\|write_todos\|run_queue\|queue.md\|getLatestRun\|runner" agent backend dashboard/src e2e` finds nothing outside tests that check it is gone
- [ ] pytest: a model's reasoning effort is its option, or `none`, and a dispatch records the model's spec and reasoning effort
- [ ] pytest: the dispatcher's nodes and edges match the table; `work_claim`'s `RetryPolicy` has three attempts on `TRANSIENT`, waiting 10 seconds first; in the tests its waits are zero, and no dispatcher test takes a second
- [ ] pytest: LangGraph's `error_handler` with two workers failing side by side, recorded as it behaves in our version, so we know which way `work_claim` goes
- [ ] Stub model test: six waiting claims at N=3, with a stub that counts the claims working at once: never more than 3, 3 at the start, each claim decided on its own thread
- [ ] Stub model test: a claim graph run by the dispatcher saves its checkpoints under its thread with no namespace, and one held for sign-off pauses without pausing the dispatch
- [ ] Stub model test: a dispatch lists the claims in progress then waiting, oldest first, and leaves decided, held, referred and left-for-a-handler claims alone
- [ ] Stub model test: a claim that hits `ModelRateLimitError` once carries on as the same attempt with one decision; one that hits it every time is tried three times, stays in progress with no `error` step, and the others finish. The same for `ModelTimeoutError`
- [ ] Stub model test: a claim that fails with another error is worked once more as attempt 2; one that fails twice is left for a handler
- [ ] Stub model test: when `start_claim` is refused, because another process started the claim, the dispatch reports it and works the rest
- [ ] Stub model test: a dispatch stopped with `KeyboardInterrupt` partway leaves its claims in progress, and the next carries them on as the same attempts, and pays a claim signed off while the service was away
- [ ] Stub model test: a dispatch started while the service resumes a claim leaves it out; Stop during a dispatch starts no more claims, lets the working ones finish, and the run shows stopped with the rest unfinished
- [ ] pytest: the pool opens at most `DATABASE_CONNECTIONS` with `timeout=120`, and each claim run's saver is its own; the backend's engine waits up to two minutes for a connection too (`pool_timeout=120`), since 25 claim agents send it requests at once
- [ ] pytest, backend: `create_dispatch` (N of 0 or 26 is 422), `record_run_claims` in order, `get_latest_dispatch` with each claim's state, decision, payout, start, seconds and cost, `finish_run` with the summary on a hand-made set of claims (paid, declined, referred, held, left for a handler, in progress, signed off but unpaid, rejected and waiting for the agent, never started), a second finish 409, `stop_runs`
- [ ] pytest, service: `start_dispatch` with N=2 runs with `max_concurrency` 2; a second start is 409 with "A dispatch or an evaluation is already running"; the lifespan marks a running run stopped; a dispatcher that fails marks the run stopped and frees the lock
- [ ] Command line: `uv run -m agent` asks for a claim id; `uv run -m agent CLM-1001` works one claim with no run
- [ ] vitest and e2e: the dispatch panel shows "No dispatch yet.", a dispatch played out through the API with its claims moving from Waiting to Decided, then Finished with its summary lines, cost and time, and a stopped dispatch
- [ ] Reseed, then Supabase MCP: the new tables are there and `todos` and `usage` aren't; restarting `npm run dev` after a dispatch created with curl leaves it Stopped
- [ ] Postman: the run operations, with the removed ones gone
- [ ] `npm run check` passes

## Phase 3: Starting and stopping a dispatch from the dashboard

Add `start_dispatch` and `stop_run` to the backend and `agent_service.py`, the form on the queue page and starts in the e2e stand-in.

- [ ] pytest, backend: `start_dispatch` with N=7 and a model asks the service once with them and writes nothing; the service's 409 comes back with its detail; an unreachable service gives 503 "The agent's service isn't running"; N of 0 or 26 is 422 and the service isn't asked. `stop_run` passes on the service's answer
- [ ] `grep -rn "UNDERCOVER_AGENT" backend --include=*.py` finds it only in `agent_service.py`
- [ ] vitest: the form offers 1 to 25 with 3 chosen and the models with `MODEL_NAME` chosen; Start posts the choices; a 409 and a 503 show in an alert; Stop shows while a dispatch runs
- [ ] e2e: choosing 7 and pressing "Start a dispatch" reaches the stand-in with `{"agents": 7, ...}`; Stop reaches it too
- [ ] Browser, with the service stopped: Start shows "The agent's service isn't running" and no dispatch appears
- [ ] Browser: a dispatch of five claims played out with curl, screenshots in light and dark mode, no console errors; reseed afterwards
- [ ] `npm run check` passes

## Phase 4: Evaluations

Seed the held-out claims and the handlers' decisions, add copies, `scoring.py`, `create_evaluation`, `list_evaluations`, `get_evaluation` and `start_evaluation`, the refusal of a review on a copy, and `start_evaluation` in the service.

- [ ] `uv run -m backend.seed` reports 25 held-out claims and 50 handlers' decisions besides what it seeds today, and Supabase MCP shows 10 of the decisions `tiny`
- [ ] pytest, scoring: each rule of the cost of mistakes, a payout 99 cents out right and $1.01 wrong, an undecided claim as a referral, and the measures of a hand-made evaluation
- [ ] pytest, backend: the held-out set's `tiny` claims at N=5 make five waiting copies with their ids in their records; the whole set 25; an unknown set 422; `list_claims` and Insights the same before and after
- [ ] pytest, backend: `get_claim` on every copy and `create_evaluation`'s response hold nothing from `handler_decisions`; a test checks `agent/api.py` has no function for the scoreboard's operations
- [ ] pytest, backend: `review_payout` on a held copy, sign-off or rejection, is 409 and changes nothing
- [ ] Stub model test through the service: an evaluation of the five `tiny` claims at N=5, with scripted decisions including one held for sign-off and one that fails twice, finishes; the queue is the same before and after; the held copy has no saved progress; `get_evaluation` gives the measures worked out by hand
- [ ] Stub model test: a dispatch after an evaluation leaves its copies alone, including one left in progress; a start of either while the other runs is 409
- [ ] `grep -rn "evals" agent backend dashboard/src e2e --include=*.py --include=*.ts --include=*.tsx` finds it only in `backend/seed.py` and tests
- [ ] Postman: the evaluation operations
- [ ] `npm run check` passes

## Phase 5: The scoreboard, and the model comparison on evaluations

Add the Scoreboard page with its form and list, an evaluation's page, the header link, and a copy's claim page without a review form. Rebuild `bench/` on evaluations.

- [ ] vitest: the Scoreboard lists evaluations newest first, measures formatted (80%, $1,600.00, $0.0125, 40 s, 2 min 41 s); the form posts the choices; refusals show
- [ ] vitest: an evaluation's page shows each claim beside the handler's, Right and Miss chips, "No decision", links to the copies; a copy's page names its evaluation and has no review form
- [ ] e2e: choosing the held-out set, the five tiny claims and 5 agents reaches the stand-in with them
- [ ] e2e: an evaluation played out through the API shows the measures worked out by hand on the Scoreboard and its page
- [ ] pytest, bench: a trial starts an evaluation through the backend, waits for it and reads its measures, with a stub service; `--estimate` and the budget still work; `bench/score.py` is gone
- [ ] Browser: the Scoreboard and an evaluation's page in light and dark mode, chips in Sea Green and Raspberry, no console errors; reseed afterwards
- [ ] `npm run check` passes

## Phase 6: The live runs, and the documents

After one reseed, with `npm run dev` running and GPT-6 Luna, the runs the brief describes, then the documents.

- [ ] Live: a dispatch at N=3 from the queue page; once three claims are decided, every process on port 8002 killed (`Get-NetTCPConnection -LocalPort 8002` then `Stop-Process -Force` on this Windows machine), which stops `npm run dev`; `npm run dev` again; the N=3 dispatch shows Stopped
- [ ] Live: a dispatch at N=25 carries on the claims left in progress as the same attempts with one decision each, and works the rest with 25 at once, which their start times show; the run takes well under the sum of its claims' times
- [ ] Live: claims worked from the start take about as long at N=25 as at N=3, from `work_times`; if not, report where the time goes from `model_calls` (each call's seconds) and the gaps between steps, keeping to 4 connections a process. Ed's run found the steps outside the model about 2.6 times slower at N=25, most likely waiting for a connection
- [ ] Live: a held claim signed off on its page shows paid within five seconds; one rejected comes back for a review
- [ ] Live: no claim fails for want of a connection, and `pg_stat_activity` never shows more than 12 `postgres` connections during the N=25 dispatch
- [ ] Live: an evaluation of the evaluation set at N=25 and one of the held-out `tiny` claims at N=5 appear on the Scoreboard with every measure, and the queue's counts are the same before and after
- [ ] Live: Langfuse's API finds the N=25 dispatch's claims together by its tag
- [ ] `docs/SPEC.md` (working the queue, what the team sees; Rules unchanged), `docs/TECH_STACK.md`, `docs/PROCESS.md` (these runs replace the five-claim cap), `docs/CODE_STANDARDS.md` (10 and 13), `docs/STATUS.md`, `CLAUDE.md` and the README describe the product as it now is
- [ ] `npm run check` passes with `.env` in place and moved out of the way

## Not in this plan

- Sending the scores to Langfuse.
- Moving to `error_handler` before a LangGraph release stops re-raising a handled error.
- Stopping a claim agent in the middle of its work: Stop starts no more claims.
- Clearing old checkpoints and old evaluations' copies; a reseed clears them.
- Telling a dispatch which claim `uv run -m agent CLM-…` is working; the backend still decides and pays it once.
- Running the agent's service in the cloud, sign-in, real payments and messages to customers.
