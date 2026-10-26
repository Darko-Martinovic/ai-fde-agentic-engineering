# Plan: durable state

This plan builds what `docs/DURABLE.md` asks for on top of our harness, in six phases. Each phase leaves `npm run check` green, is reviewed by a fresh subagent and is committed before the next one starts.

SIDENOTE: For consistency with the course, please read `labs/week2day3.ipynb` and build the solution in the same style as the lab. Where the lab and this brief differ, follow the brief. Include this sidenote in your plan too.

When it's done, the backend works out payouts with UnderCover's payout rules and keeps its records in Supabase. The claim agent is a LangGraph graph that saves its progress in the same database after every step. An approval over the limit pauses the graph, and a handler's sign-off on the dashboard reaches the agent's own service, which picks the claim up and pays it. A claim stopped partway carries on from its last step, and the backend makes sure nothing is decided or paid twice. Every claim's work is traced in Langfuse, one session per claim and thread.

The student added one thing to the brief: a handler can also reject a held payout, with a note, as well as sign it off. The brief leaves rejecting for later; the student wants both ways for a handler in the loop now. "A handler signs off or rejects" below says how it works.

At the student's request, Ed's `upstream/week2day3-end` was read before this plan was written. His build starts from a different codebase (one `database.py`, one `main.py`, no dashboard Run and Stop), so this plan follows his design where it fits ours and says where it differs.

## Design

### What changes, in one picture

```
dashboard ──/api──> backend (FastAPI) ──SQLAlchemy Core──> Supabase, schema "undercover"
                       │   sign-off saved, then                (SQLite in the tests)
                       │   POST /api/claims/{id}/resume
                       v
                   agent service (FastAPI, port 8002) ──┐
                                                         ├── claim graph ── PostgresSaver ──> Supabase, schema "undercover"
   uv run -m agent (queue or named claims) ─────────────┘        │
                                                                 └── agent/api.py ──> backend
```

### Modules

The backend:

- `db.py`: the tables as SQLAlchemy `Table` objects in one `MetaData`, and the engine. It is the only module that reads `DATABASE_URL`, `UNDERCOVER_DB` and `DATABASE_SCHEMA`. With `DATABASE_URL` set (and not empty) the engine is `postgresql+psycopg`, with `search_path` set to the schema on every connection, a pool of `DATABASE_CONNECTIONS` (3) with no overflow and `pool_pre_ping`. Without it, SQLite at `UNDERCOVER_DB` with `NullPool`, as today. The engine is made on first use (`functools.cache`), so a process that never touches the database, such as the agent's process the runner spawns, never opens a connection.
- `store/` (`claims.py`, `records.py`, `runs.py`, `steps.py`): every query rewritten as a Core expression, written once for SQLite and Postgres. The function names and what they return stay, so the routes barely change. Records stay JSON text, as today.
- `api.py`: the `Db` dependency yields a SQLAlchemy `Connection` inside `engine.begin()`, with `scope="function"`, so a request's work is committed before the response is sent and before a background task runs. Seeding stays with the dependency, done once a process (`seed.ready`, cached by engine), rather than in the app's lifespan: the tests use `TestClient(app)` without a `with`, which never runs a lifespan, and each test has a database of its own. A database without its tables, or without claims, is seeded afresh.
- `runner.py`: Run starts the agent's process in a background task, so the process finds the queue as the request committed it.
- `seed.py`: on Postgres, creates the schema if it's missing; on both, drops and creates the backend's tables and loads `data/`. It leaves the checkpointer's tables alone, since a reseeded claim always gets a new thread. `uv run -m backend.seed` seeds whichever database the settings name, Supabase when `.env` has `DATABASE_URL`.
- `payout.py` (new): the payout rules from `labs/week2day1_payout.py`, as plain functions of a policy, the plans and the company's settings. It reads nothing from `data/` and imports only `models.py`.
- `claims.py`: gains the `calculate_payout` operation (a claim's payout belongs with the claim).
- `workflow.py`: idempotent decision and payment, the new sign-off, `fail_claim` refusing a decided claim.
- `agent_service.py` (new): the backend's one call to the agent's service, at `UNDERCOVER_AGENT`.
- `runner.py`: Stop no longer puts the claim back in the queue; it stays in progress with its saved progress, for the next run to carry on.

The agent. The brief makes the service a fourth part beside `api.py`, `tools.py` and `harness.py`, and the graph's nodes take the place of the claim agent's middleware:

- `api.py`: gains `calculate_payout`. One function per backend operation, as today.
- `tools.py`: gains `calculate_payout`; `pay_claim` leaves the claim agent's tools. `decide_claim` returns a `Command` that adds its tool message and puts the backend's status and decision in the graph's state (LangGraph's way for a tool to update state). Gains `ClaimState`.
- `graph.py` (new): the claim graph: its nodes, its edges and `claim_graph(llm, model, saver)`. This is what `middleware.py` did for the claim agent.
- `recording.py` (new): what the agents record on the backend, a reply's steps and a model call's usage. The graph's nodes and the queue agent's `UsageRecorder` both use it, so it is a module of its own rather than a helper borrowed from either.
- `middleware.py`: keeps `UsageRecorder` and `refusal` for the queue agent, which stays on `create_agent`. `StepRecorder` goes.
- `checkpoints.py` (new): `saver()`, a context manager that opens a `psycopg_pool.ConnectionPool` on `DATABASE_URL` (1 to `DATABASE_CONNECTIONS` connections, `autocommit=True`, `prepare_threshold=0`, `row_factory=dict_row`, `search_path` set to the schema), creates the schema, runs `setup()` and yields a `PostgresSaver`. It refuses to start without `DATABASE_URL`, since an agent without saved progress can't be picked up by the service. Tests pass an `InMemorySaver` instead and never open it.
- `harness.py`: the model, the claim graph for each claim, `work_claim`, `carry_on` and `carry_on_stopped`. The claim agent's build moves to `graph.py`.
- `queue_agent.py` (new): the queue agent on `create_agent`, its middleware and `run_queue`, moved out of `harness.py` to keep both under 300 lines.
- `service.py` (new): the agent's service, a small FastAPI app with `health` and `resume_claim`, run with `uv run -m agent.service` on `AGENT_HOST` and `AGENT_PORT`.
- `tracing.py`: claim sessions (below).
- `__main__.py`: opens the saver, builds the claim graph and works the claims or the queue.

Dependencies: the agent reaches the backend only through `api.py`, the backend reaches the agent's service only through `agent_service.py`, the dashboard reaches the backend only through `api.ts`. Inside the agent: `service` and `__main__` use `harness`; `harness` uses `graph`, `checkpoints`, `tools`, `api` and `tracing`; `graph` uses `tools`, `recording` and `api`; `middleware` uses `recording`; `recording` and `tools` use `api`. `backend/runner.py` keeps importing `agent.__main__`, as today.

### Settings

`.env.defaults` gains, so no address, port, schema or pool size is written in code:

```
AGENT_HOST=127.0.0.1
AGENT_PORT=8002
UNDERCOVER_AGENT=http://${AGENT_HOST}:${AGENT_PORT}
E2E_AGENT_PORT=8003
E2E_AGENT_URL=http://${AGENT_HOST}:${E2E_AGENT_PORT}
DATABASE_SCHEMA=undercover
DATABASE_CONNECTIONS=4
```

`DATABASE_URL` stays in `.env` only. The root `conftest.py` removes it from the environment, and the end-to-end servers get it empty, so the tests never connect.

### How a claim is worked

1. `work_claim` starts the claim as a new attempt with a new thread id (`CLM-1001-<8 hex>`, as today) and runs the claim graph on that thread.
2. The claim agent reads the claim, looks up the sections it needs, works out an approval's payout with `calculate_payout` and records its decision with `decide_claim`.
3. A decline or a referral ends the graph. For an approval, the graph follows the backend's reply: `in_progress` goes to `pay`; `awaiting_sign_off` goes to `wait_for_sign_off`, which pauses with `interrupt()`, and `work_claim` reports the claim as waiting for a sign-off. The graph never compares the payout with the limit.
4. A handler signs off on the dashboard, or rejects the payout with a note. The backend records the review (who, when, the note), moves the claim to `in_progress` and, once that is committed, asks the agent's service to resume it. After a sign-off the graph pays the claim, and the payment records the handler and the time of the sign-off. After a rejection the agent gets the handler's note and looks at the claim again.
5. If the agent is stopped at any point (a crash, Ctrl-C, Stop on the dashboard) the claim stays `in_progress` with its progress saved. The next run carries it on from its last saved step, on the same thread and attempt, before it does anything else.
6. A claim that fails with an error before it is decided goes back in the queue and starts afresh, as today. A claim with a decision is never failed: an approval whose payment failed stays in progress, and the next run pays it.

### Claim states

The states stay as they are: `waiting`, `in_progress`, `awaiting_sign_off`, `referred`, `left_for_handler` and `decided`. Two moves change:

- `awaiting_sign_off` → `in_progress` on a sign-off (it went straight to `decided` before), and `in_progress` → `decided` when the graph pays.
- `awaiting_sign_off` → `in_progress` on a first rejection, while the agent looks again; `awaiting_sign_off` → `referred` on a second.
- Stop leaves a claim `in_progress` (it went back to `waiting` before).

An approval within the limit already stays `in_progress` until it is paid, so nothing changes there.

### The claim graph

`ClaimState`, a `TypedDict` as in the lab:

- `messages`, with `add_messages`
- `model_calls`: the model calls made so far, saved with the rest, so the limit of 30 holds across a restart
- `decision` and `status`: set by `decide_claim`'s `Command` from the backend's reply

The claim id, thread id and run id stay in `ClaimContext`, passed with `context=` on every invoke, so the tools still act only on their own claim.

The nodes:

| Node | What it does |
| --- | --- |
| `agent` | Calls the model, with the claim instructions as the system message and the tools bound, as `create_agent`'s model node does. Records the reply and its tool calls as steps and the call's usage on the run, and adds one to `model_calls`. Raises `TooManyModelCalls` before a 31st call. Provider errors are retried twice by the model's own `with_retry`, in place of `ModelRetryMiddleware`, so only the model call is tried again, never the recording around it |
| `tools` | `ToolNode(CLAIM_TOOLS)` with `wrap_tool_call`, which gives the backend's refusals (and a tool called the wrong way) back to the model as text, as `ToolErrorMiddleware` does today, and records each tool result, and each section read, as steps. The refusals are handled in the wrapper, not with `handle_tool_errors`: with a wrapper, ToolNode 1.2 gives every error back to the model, so a broken backend would no longer fail the claim |
| `wait_for_sign_off` | Pauses with `interrupt()`; nothing comes before it, since a resumed node runs again from the top. The resume value is the handler's review: a sign-off moves on to `pay`; a rejection adds the handler's note to the messages, clears `decision` and `status`, and the graph goes back to `agent` |
| `pay` | Pays the decision's payout with `pay_claim` and sets `status` from the reply |

The edges:

| From | To | When |
| --- | --- | --- |
| START | `agent` | always |
| `agent` | `tools` | the reply calls tools |
| `agent` | END | no tool calls: the agent stopped without a decision, which the harness fails |
| `tools` | `agent` | no decision recorded yet |
| `tools` | `wait_for_sign_off` | `status` is `awaiting_sign_off` |
| `tools` | `pay` | an approval with `status` `in_progress` |
| `tools` | END | a decline or a referral |
| `wait_for_sign_off` | `pay` | the handler signed off |
| `wait_for_sign_off` | `agent` | the handler rejected the payout |
| `pay` | END | always |

Every invoke passes `durability="sync"`, so each step's checkpoint is saved before the next step starts. LangGraph 1.2's recursion limit is 10,007 steps (`DEFAULT_RECURSION_LIMIT`), so `model_calls` is the real limit.

### Following the lab

As in the lab: a `TypedDict` state with `add_messages`; an `agent` node that calls the model with the tools bound; LangGraph's `ToolNode`; conditional edge functions named `after_agent` and `after_tools`; the pause in a node of its own; the payment in a node of its own; `PostgresSaver` with `autocommit=True`, `prepare_threshold=0` and `row_factory=dict_row` and the schema set with `search_path`; `durability="sync"`; `Command(resume=...)`; and `get_state()` with its `next`.

Where the brief differs, we follow the brief:

- The agent records its decision with the `decide_claim` tool, so there is no separate decide node with structured output.
- The graph pauses when the backend says the claim waits for a sign-off, never on its own comparison with the limit.
- The backend's `pay_claim` pays, and refuses a payout over the limit without a sign-off, in place of the lab's `payments` table.
- Each attempt has its own thread id, in place of the claim id.
- A pool of at most 3 connections in each process (the brief allows 4), in place of the lab's single connection, and the `undercover` schema.

### Carrying on

`carry_on(claim_id, graph, run_id)` picks up an in-progress claim on the thread of its latest attempt, without a new attempt:

- Thread waiting at `wait_for_sign_off`: a handler has reviewed the claim, so it resumes with `Command(resume=review)`, the review read from the backend's latest decision (signed off, or rejected with its note). The backend holds the truth; the graph only carries it.
- Thread with nothing saved, because the agent was stopped before its first checkpoint: it starts the graph from the beginning on the same thread.
- Otherwise: it invokes the graph with no input, which carries on from the last saved step.

`work_claim` and `carry_on` share one function that invokes the graph and settles the claim, as `work_claim` does today: any exception is caught so one bad claim never stops a run; a claim still in progress with no decision is failed with `fail_claim`; a claim with a decision is never failed; the report line is built from the backend's record, with one new outcome, "approved $420.00, not paid yet".

Every run of `uv run -m agent`, the queue or named claims, first:

1. finishes the latest run if it's still running, with the summary "The run stopped before it finished.";
2. carries on every claim in progress and prints each report. These don't count toward the cap. This replaces the runner's `return_to_queue`.

To carry on, the agent needs a claim's thread and attempts: the claim record gains `thread_id` (its latest attempt's) and `attempts`.

As today, two processes can't tell a stopped claim from one the other is working at that moment. The agent's service only ever resumes the claim it was asked to, and the backend pays a claim once even if both pick it up.

### Nothing happens twice

- `decide_claim` on a claim with a decision returns the claim when the decision and payout are the same, and refuses anything else with 409.
- `pay_claim` on a claim already paid returns the claim when the amount is the same, and refuses a different amount with 409.

- Two requests at once can't both record: each claim keeps a `revision`, and a decision or payment moves the claim on only from the revision it read (`claims.move`, a conditional `UPDATE`, as `claims.start` does). The one that loses reads the claim again and is a repeat or a refusal. This matters because ToolNode runs a reply's tool calls side by side, so a reply with `decide_claim` twice reaches the backend twice at once; the graph's `decision` and `status` keep the latest value for the same reason.

A restart can still record a step twice on the timeline, when the agent was stopped between recording the step and saving the checkpoint. That is the only repeat.

### A handler signs off or rejects

The student's addition. A held approval has two answers on the dashboard:

- **Sign off and pay**: as the brief describes. The agent pays the claim, with the handler and the time on the payment.
- **Reject**, with a note that says what's wrong, such as "The suit is limited to $300.00 under the per-item limit". The rejection is recorded on the decision (`review` `rejected`, `reviewed_by`, `reviewed_at`, `review_note`), the claim goes back to `in_progress`, and the agent's service resumes the graph with the note, which reaches the agent as a message. The agent looks at the claim again and records a new decision.

Rules the backend enforces, as our Week 2 Day 3 challenge found they must be:

- After a rejection, the agent's next decision always goes back to a handler: an approval of any size waits for a sign-off, and a decline or a referral is `referred`, for a handler to decide. A handler rejected the agent's work once, so the agent never closes the claim alone.
- A second rejection refers the claim to a handler, with no payout and no resume. A handler then decides it with the form for referred claims.
- A rejection needs a note (422 without one) and a known handler (404).
- A claim that fails with an error after a rejection is left for a handler, keeping its decisions, rather than starting afresh. So is one where the agent answers the note without recording a decision again.

The sign-off and the rejection are one operation, `review_payout`, so a review is recorded and handed to the agent in one way. The dashboard's form gains a note and a Reject button beside Sign off.

### The payout rules

- `backend/payout.py` holds the rules from `labs/week2day1_payout.py`: the per-item limit by quantity, electronics with and without Electronics Plus, cash up to $100 in all, hotel nights by rooms, meals without receipts per traveler per day, what others have paid, the deductible for the benefits in `deductible_applies_to`, the benefit maximum (capped at the trip cost for cancellation and interruption), and nothing below zero.
- The plans and add-ons come from `plans.json` and the approval limit and meal allowance from `company.json`, both already seeded into `settings`. Cash and hotel limits stay named constants, citing their sections, since `data/` doesn't hold them. `needs_sign_off` follows the stored limit.
- `calculate_payout`, `POST /api/claims/{claim_id}/payout`, body `{benefit, lines, paid_by_others}`, every field of a line required (`description`, `amount`, `quantity`, `kind`, `nights`, `hours`). It works out the payout on the claim's policy and records nothing. It returns `{calculation: [{step, amount}], payout, needs_sign_off}`. 404 for an unknown claim, 422 for a bad benefit, kind, quantity or missing field.
- The lab's file stays in `labs/` as it is.

### Tracing

- Each invoke of the claim graph is a trace of its own, `work-claim` for an attempt's first run and `carry-on` for a restart or a sign-off, in the session named after the claim's thread (`CLM-1008-6f1c2a9b`, the claim and its thread). So the first run, a carry-on after a restart and the payment after a sign-off sit together in one session.
- To make it a trace of its own inside a queue run, the harness runs the claim graph in a fresh `contextvars.Context`, so neither LangChain's parent run nor Langfuse's current span carries over.
- The queue run stays one `run-queue` trace, with no session (sessions are for claims), each `work_claim` tool call's output the claim's report, which names the claim. This changes what we built on October 22, when claim agents were nested inside the queue trace; the brief's per-claim session can't hold work that sits inside another trace.
- Keys from `.env`; the tests send nothing.

### The database

- Tables: `claims`, `policies`, `customers`, `handlers`, `settings`, `steps`, `decisions`, `runs`, `attempts`, `usage`, `payments`, as today. `decisions` gains `signed_off_by` and `signed_off_at`, and `payments` gains `signed_off_at`. Integer ids stay, with `RETURNING` in place of `lastrowid`.
- Connections: Supabase's free plan allows 15 clients through the session pooler. The backend, the agent's service and a run each hold at most 3, so at most 9: the brief allows 4 each, but the pooler keeps server connections a while after a process ends, and a check in phase 4 hit its limit of 15 with 4 each while processes were restarted, so each process keeps one in hand.

### API

New and changed operations. Every operation keeps an `operation_id`, a one-line docstring and no optional inputs.

| Operation | Change |
| --- | --- |
| `calculate_payout` | New, as above |
| `decide_claim` | A repeat of the same decision returns the claim |
| `decide_claim` after a rejection | Allowed on the claim in progress; an approval waits for a sign-off whatever its size, a decline or a referral is `referred` |
| `pay_claim` | A repeat of the same amount returns the claim. Over the limit, or after a rejection, it needs a sign-off on the decision (409 without one, as today). The payment's `authorized_by` is the handler who signed off, or `agent`, and `signed_off_at` the time of the sign-off |
| `review_payout` (was `sign_off_claim`, in `backend/reviews.py` with `decide_as_handler`; the rules both routers follow are in `backend/claim_rules.py`) | `POST /api/claims/{claim_id}/review`, body `{handler_id, approved, note}` (`note` may be empty for a sign-off, never for a rejection). Records the review on the decision and moves the claim to `in_progress`, or to `referred` on a second rejection; pays nothing. A FastAPI background task then calls the agent's service, after the commit and the response, unless the claim was referred. If the service can't be reached, the backend logs a warning and the review stands |
| `fail_claim` | Also refuses a claim that has a decision |
| `get_claim`, `list_claims` | The claim gains `run_id` and `thread_id` (of its latest attempt) and `attempts`; the decision `review`, `reviewed_by`, `reviewed_at` and `review_note`; the payment `signed_off_at` |
| `run_claim` | Accepts a claim in progress too, which the run carries on |

The agent's service, at `UNDERCOVER_AGENT`:

| Operation | Route | What it does |
| --- | --- | --- |
| `health` | `GET /api/health` | `{"status": "ok"}` |
| `resume_claim` | `POST /api/claims/{claim_id}/resume` | "Pick a claim back up after a handler's review." 409 for a claim that isn't in progress; otherwise 202 at once, carrying the claim on in a background task and logging the report |

Its lifespan opens the saver; a dependency builds the claim graph on `MODEL_NAME` for each request, so the service needs no backend at startup and picks up changed instructions. Resuming a signed-off claim makes no model call; after a rejection the agent works again on `MODEL_NAME`, its usage recorded on the claim's run. A new test checks the OpenAPI rules (operation id, one-line docstring, no optional input, nested models included) for both apps.

### Instructions

- **Working a claim**, as goals: an approval's payout is worked out with `calculate_payout`, which applies UnderCover's payout rules, and the decision records the payout it returns. Which lines are covered, and what counts as one item, are the agent's judgment. The system pays an approval, after a handler's sign-off when it is over the limit. A handler may reject a held payout with a note: the agent takes the note into account and records a fresh decision, which a handler then reviews. `pay_claim` is no longer mentioned.
- **Running the queue**: unchanged, apart from a report that says "not paid yet".

### Dashboard

- The decision panel: an approval in progress without a payment says "Waiting for the agent to pay it"; after a sign-off, "Signed off by Dana Whitfield at 2:05 PM"; a payment after a sign-off, "Paid $1,350.00, signed off by Dana Whitfield at 2:05 PM"; a rejected decision, "Rejected by Dana Whitfield at 2:05 PM: <note>", above the agent's new decision.
- The review form: the handler, a note, and two buttons, "Sign off $1,350.00" and "Reject". Reject needs a note.
- `claimTypes.ts` gains the new fields. The queue and claim pages already poll, so the payment shows without a reload.
- Stop's tooltip and the run panel stop saying a stopped claim goes back to waiting.

### End-to-end tests

- Playwright starts a stand-in for the agent's service, `e2e/agent_stand_in.ts` (Node's own TypeScript), on `E2E_AGENT_PORT` (8003). It answers `health` and `resume_claim` with 202, and lists the claims it was asked to resume at `GET /api/resumed`. The e2e backend gets `UNDERCOVER_AGENT` set to it and `DATABASE_URL` empty, so the tests never reach the real service or Supabase.
- The sign-off test signs off a held claim on the dashboard, sees In progress and "Signed off by", checks the stand-in was asked to resume it, then plays the agent by paying through the API and sees Decided and "Paid ... signed off by" without a reload.
- The rejection test rejects a held claim with a note, sees In progress and "Rejected by ... : <note>", and checks the stand-in was asked to resume it.

### Checked against the code standards

- One way to call each service, each address written once: `agent/api.py`, `dashboard/src/api.ts`, `backend/agent_service.py`, and the stand-in's address in the e2e settings. `tests/test_standards.py` gains `backend/agent_service.py` as the backend's only HTTP client.
- One owner for each setting: `DATABASE_URL` and the schema are read by `backend/db.py` and `agent/checkpoints.py`, the backend's and the agent's own connection, since neither imports the other; the schema name and pool size are written once, in `.env.defaults`.
- All SQL stays in `backend/store/`, now as Core expressions; `db.py` holds the schema.
- Modules keep to their jobs: rules in `payout.py`, the graph in `graph.py`, saving progress in `checkpoints.py`, recording in `recording.py`, the service only receives the backend's call and hands it to the harness. `harness.py` stays under 300 lines.
- The framework's own way: `StateGraph`, `ToolNode` with `wrap_tool_call`, the model's `with_retry`, `Command` from a tool, `interrupt()` and `Command(resume=...)`, `PostgresSaver` on a `ConnectionPool`, `durability="sync"`, FastAPI's `BackgroundTasks`, lifespan and dependency `scope`, SQLAlchemy Core, Langfuse's `CallbackHandler` and `propagate_attributes`.
- Instructions stay goals. What must always happen in order, paying after the decision and after a sign-off, is done by the graph.
- No defensive code beyond the brief: the harness keeps its one catch around a claim, and the backend catches only a failure to reach the agent's service, because the sign-off must stand.

### How the criteria are checked

API calls run against `npm run dev` after a reseed: SQLite in phase 1, Supabase from phase 2. Tables and connections are checked through the Supabase MCP server (read-only), Langfuse through its API with a short `uv run python -c`, pages with the Playwright MCP server at `http://localhost:5173`. Tests never call a model and need no network. Only criteria marked "Live" use the real model, on the default model, straight after a reseed and on at most five claims.

## Phase 1: The payout rules and tracing

Bring in `backend/payout.py`, the `calculate_payout` operation and tool, and the new claim instructions. Move each claim's work into a trace of its own in the claim's session. Add the OpenAPI rules test.

- [x] `calculate_payout` on `CLM-1001` with a hotel of 245.00 for one night and two expenses of 95.00 and 80.00 under `trip_delay` returns 420.0, no deductible, `needs_sign_off` false
- [x] On `CLM-1003`, one expense of 3,800.00 under `emergency_medical` returns 3,750.0 with "Less the deductible" and `needs_sign_off` true
- [x] On `CLM-1007`, a smartphone of 1,099.00 (`electronics`) under `baggage` returns the step "Smartphone, limited to $150.00" and a payout of 50.0
- [x] A line without `nights` returns 422, a benefit of `pets` returns 422, `CLM-9999` returns 404
- [x] pytest covers every rule: each kind of line, the deductible only for the benefits in `deductible_applies_to`, the cap at the trip cost, a payout that would fall below zero, and with the stored limit changed to 500, a payout of 550.00 needs sign-off
- [x] `grep -rn "1000\|data/" backend/payout.py` finds nothing
- [x] The OpenAPI rules test passes, and fails on a request model with an optional field nested in its body
- [x] A pytest test checks the claim agent's tools are `get_claim`, `get_policy`, `get_customer`, `search_documents`, `read_section`, `calculate_payout`, `decide_claim` and `pay_claim` (until phase 3)
- [x] Stub model test: the stub calls `calculate_payout` for `CLM-1001`, and the tool result recorded on the claim holds payout 420.0
- [x] `curl -s localhost:8000/api/instructions/claim` names `calculate_payout`
- [x] Stub model test with spans in memory: a claim worked on the command line is a root `work-claim` trace in the session named after its thread
- [x] The same inside a queue run of two claims: two `work-claim` traces, each a root in its own claim's session, beside the `run-queue` trace
- [x] Postman: `calculate_payout` requests for the four cases above, and the collection passes against the dev backend after a reseed
- [x] Live: after reseeding, `uv run -m agent CLM-1001` decides the claim, its steps include a `calculate_payout` call, and the decision's payout equals what the tool returned
- [x] Live: through Langfuse's API, the session named after `CLM-1001`'s thread has a `work-claim` trace with at least two model calls
- [x] `npm run check` passes

## Phase 2: Our records on Supabase

`uv add sqlalchemy psycopg-pool`. Rewrite `backend/db.py` and `backend/store/` with SQLAlchemy Core, seed on startup and with `uv run -m backend.seed` on either database, and point the backend at Supabase when `DATABASE_URL` is set.

- [x] `grep -rn "sqlite3" backend` finds nothing outside `backend/db.py`
- [x] pytest, without connecting: with `DATABASE_URL` set to a Postgres address, the engine is `postgresql+psycopg`, a pool of 4 with no overflow, with `search_path` set to `undercover`; without it, SQLite at `UNDERCOVER_DB`
- [x] `DATABASE_URL=postgresql://nobody:x@127.0.0.1:1/none npm run check:python` passes: the tests remove it and never connect
- [x] pytest: the backend seeds an empty SQLite file on startup, and two runs started together come back from `get_latest_run` in the order they started
- [x] `uv run -m backend.seed`, with `DATABASE_URL` in `.env`, prints "Reset the undercover schema on Postgres", and twice in a row gives the same result
- [x] Supabase MCP: `list_tables` for `undercover` shows the backend's eleven tables and none in `public`; `select status, count(*) from undercover.claims group by status` gives 25 `waiting`
- [x] With `npm run dev` running on Supabase: `curl -s localhost:8000/api/claims` returns 25 claims, `CLM-1001` first, and `/api/claims/CLM-1001` its story, items and documents
- [x] Walked through with curl on Supabase: start `CLM-1004` in a run and decline it, and it is `decided`; Supabase MCP shows its row in `undercover.decisions`; a reseed puts it back to `waiting`
- [x] Supabase MCP, with the dashboard open for 30 seconds: `select count(*) from pg_stat_activity where usename = 'postgres'` is at most 5
- [x] Supabase MCP: `get_advisors` (security) lists nothing about the `undercover` schema, and `list_tables` shows row level security on for each table
- [x] Browser: the queue shows 25 claims and Insights loads, with no console errors
- [x] Postman collection passes against Supabase after a reseed
- [x] Live: `uv run -m agent CLM-1001` decides the claim, and Supabase MCP shows its decision and steps in `undercover`
- [x] `npm run check` passes with `.env` in place and with it moved out of the way

## Phase 3: The claim agent as a graph that saves its progress

Replace the claim agent's `create_agent` and middleware with the graph, saved by the Postgres checkpointer. Remove the `pay_claim` tool and update the instructions. In the backend: idempotent decision and payment, `fail_claim` refusing a decided claim, and the claim's `thread_id` and `attempts`. The sign-off still pays until phase 4, so a paused thread is left behind.

- [x] A pytest test checks the graph's nodes and edges against the tables above
- [x] The claim agent's tools are `get_claim`, `get_policy`, `get_customer`, `search_documents`, `read_section`, `calculate_payout` and `decide_claim`
- [x] pytest, backend: approving `CLM-1001` for 420.00 leaves it `in_progress`; the same decision again returns the claim with one decision; 400.00 returns 409. Paying 420.00 decides it; paying 420.00 again returns the claim with one payment; 400.00 returns 409
- [x] pytest, backend: `fail_claim` on a decided approval in progress returns 409 and changes nothing
- [x] Stub model test, within the limit: the stub works out and approves 420.00; the graph pays it with no `pay_claim` tool call, the model isn't called after the decision, and the report is "CLM-1001: approved $420.00, paid"
- [x] Stub model test, over the limit: the stub approves `CLM-1003` for 3,750.00; the report says waiting for a handler's sign-off, `get_state` shows `next` as `("wait_for_sign_off",)`, and there is no payment
- [x] Stub model test: with the stored limit raised to 5,000, the same approval is paid at once, since the graph follows the backend
- [x] Stub model tests: a decline and a referral end with no payment and no `pay` step in the state history
- [x] The existing harness tests pass on the graph: steps in order, section steps, a refusal going back to the model, a read of section 15 or of a `handbook` going back to the model
- [x] Stub model test: a stub that calls `get_claim` forever stops at 30 model calls with "TooManyModelCalls", and the claim is back in the queue
- [x] Stub model test: a provider error is retried twice; a third failure puts the claim back in the queue, the next attempt is on a new thread, and a second failure leaves it for a handler
- [x] Stub model test: when paying raises an error, the claim stays `in_progress` with its decision and the report ends "not paid yet"
- [x] A test checks every claim graph invoke passes `durability="sync"` and a Langfuse handler
- [x] Usage: a stub run records one usage row per model call on the run, with the claim
- [x] `curl -s localhost:8000/api/instructions/claim | grep -c pay_claim` prints 0
- [x] Live: after a reseed, `uv run -m agent CLM-1001` approves and pays with no `pay_claim` call in its steps; Supabase MCP shows the checkpointer's tables in `undercover` and rows in `undercover.checkpoints` for the claim's thread
- [x] Live: after a reseed, `uv run -m agent CLM-1003` reports waiting for sign-off; Supabase MCP shows an `__interrupt__` write in `undercover.checkpoint_writes` for its thread
- [x] `npm run check` passes

## Phase 4: A sign-off or a rejection picks the claim back up

`review_payout` in place of `sign_off_claim`, `backend/agent_service.py`, `agent/service.py` in `npm run dev`, `carry_on` for a reviewed thread, the review form and decision panel, the e2e stand-in, and the Postman workflow.

- [x] pytest, backend: signing off `CLM-1003`'s held 3,750.00 as `HND-01` returns it `in_progress` with the decision signed off by `HND-01` at a time and no payment; paying 3,750.00 decides it, with a payment authorized by `HND-01` at the time of the sign-off; the 404 and 409 rules still hold
- [x] pytest, backend: rejecting with a note returns the claim `in_progress` with the decision rejected, by whom, when and the note; a rejection with an empty note returns 422; the agent's next approval of 500.00 waits for a sign-off; its next decline is `referred`; a second rejection makes the claim `referred` and the service is not told
- [x] pytest, backend: a failure after a rejection leaves the claim for a handler with its decisions
- [x] pytest, backend: the agent's service is told once, for `CLM-1003`, and only after the sign-off is committed (the fake service reads the claim and finds the sign-off)
- [x] pytest, backend: when the service can't be reached, the sign-off returns 200 and stands, and a warning is logged
- [x] pytest, backend: `pay_claim` on a held claim with no sign-off returns 409 and records nothing
- [x] Stub model test, the whole sign-off: the graph pauses; after the sign-off, `resume_claim` returns 202 and the claim is `decided` with one payment by `HND-01`; the model isn't called again; the carry-on is a `carry-on` trace in the claim's session. A second `resume_claim` returns 409 and there is still one payment
- [x] Stub model test, a rejection: the graph pauses on 3,750.00; after a rejection with a note, `resume_claim` carries the claim on, the stub's next prompt ends with the handler's note, it approves 3,700.00, and the graph pauses again with the claim `awaiting_sign_off` and no payment; a sign-off then pays 3,700.00 once
- [x] `resume_claim` on a claim awaiting sign-off returns 409 and changes nothing
- [x] The OpenAPI rules test passes for the agent's service
- [x] With `npm run dev` running, `curl -s localhost:8002/api/health` returns `{"status":"ok"}`, beside the backend on 8000 and the dashboard on 5173
- [x] `grep -rn "UNDERCOVER_AGENT\|httpx" backend --include=*.py` finds them only in `backend/agent_service.py` and its test
- [x] vitest: the decision panel for an approval waiting for its payment, a signed-off claim waiting for its payment, a payment with its sign-off and a rejected decision with its note; the review form sends a sign-off, sends a rejection with its note, and won't reject without a note
- [x] e2e, sign-off and rejection: as in the design, against the stand-in on 8003
- [x] Browser: screenshots of the review form, a payment after a sign-off and a rejected payout (`docs/screenshots/durable-*.png`), in the brand, no console errors; the signed-off claim waiting for its payment is taken in phase 5, with the service stopped
- [x] Postman: the Workflow folder signs off, sees `in_progress`, pays, and repeats the decision and payment to see them return the claim; and rejects another held claim with a note
- [x] Live: after a reseed, `uv run -m agent CLM-1003` waits for sign-off; signing off on `/claims/CLM-1003` as Dana Whitfield shows Decided and "Paid", with the handler and the time, within five seconds, and the service logs the report line
- [x] Live: through Langfuse's API, `CLM-1003`'s session has a `work-claim` trace from before the sign-off and a `carry-on` trace from after it
- [x] Live: after a reseed, `uv run -m agent CLM-1011` waits for sign-off; rejecting it on the dashboard with a note naming the rule makes the agent decide again within a minute, and its new decision waits for a sign-off
- [x] `npm run check` passes

## Phase 5: Work survives a restart

`carry_on` for a claim stopped partway, every run first finishing a stopped run and carrying on claims in progress, and Stop leaving the claim in progress. The tests stop the agent with `KeyboardInterrupt`, which the harness doesn't catch, so the claim is left as a crash leaves it.

- [x] Stub model test: the stub reads the claim and its policy, then raises `KeyboardInterrupt`; the claim is `in_progress`, attempts 1. A new graph on the same saver with a new stub carries it on: same thread, attempts 1, the new stub's first prompt holds the two earlier tool results, the steps carry on under the same thread with no failure step, and one decision
- [x] Stub model test: stopped just after the backend records the decision, the claim carries on and is paid once
- [x] Stub model test: stopped just after the backend records the payment, the `pay` step runs again and there is still one payment
- [x] Stub model test: a claim in progress with no checkpoint starts from the beginning on its own thread, attempts unchanged
- [x] Stub model test: 20 model calls before the stop and an endless `get_claim` after it stop at 30 in all
- [x] Stub model test: a claim that fails with an error while carried on goes back in the queue, and the next `work_claim` is attempt 2 on a new thread
- [x] Stub model test, a queue run: one claim stopped partway and one signed off while the agent was away are carried on and reported before the queue agent starts, and neither counts toward the cap
- [x] Stub model test: when the latest run is still running, a new run finishes it with "The run stopped before it finished."
- [x] With nothing waiting, `uv run -m agent` still carries on a claim in progress, then prints "No claims are waiting."
- [x] pytest, runner: Stop ends the process and marks the run stopped, and the claim stays `in_progress` with its steps; `run_claim` accepts a claim in progress
- [x] `uv run -m bench --estimate` still works, and the bench tests pass
- [x] Live: after a reseed, start `uv run -m agent --cap 1`; once the claim shows at least four steps, kill the agent's process. `uv run -m agent --cap 1` again prints that claim's report first: same thread, attempts 1, one decision, steps from both runs under that thread, and the stopped run says "The run stopped before it finished."
- [x] Live: after a reseed, with only the backend and dashboard running (no service), `uv run -m agent CLM-1003` waits for sign-off; signing off leaves it In progress and the backend logs a warning; the next `uv run -m agent --cap 1` pays it first, with the sign-off on the payment
- [x] Live, dashboard: Run 1, then Stop partway; the claim shows In progress; Run 1 again carries it on to a decision
- [x] `npm run check` passes

## Phase 6: A trial on five claims, and the documents

Run the trial the brief describes, then bring the documents up to date.

- [ ] Live: after a reseed, with `npm run dev` running, Run 5 on the default model works five claims and the run finishes with its summary; at least one waits for sign-off
- [ ] Live, in the browser with the Playwright MCP server: signing off a held claim as Dana Whitfield shows it Decided and paid, with the handler and the time, within five seconds
- [ ] Live: Supabase MCP, checked several times during the run and the sign-off, never shows more than 12 `postgres` connections in `pg_stat_activity`
- [ ] Live: through Langfuse's API, the held claim's session has traces from before and after the sign-off
- [ ] Live: afterwards the queue shows 20 waiting and none in progress
- [ ] `docs/SPEC.md`: its section on working the queue describes the pause for a sign-off, the agent picking the claim up after it, carrying on after a restart without a new attempt, and nothing decided or paid twice; its Rules are unchanged
- [ ] `docs/TECH_STACK.md`: SQLAlchemy Core on Supabase with SQLite in the tests, the claim graph with the Postgres checkpointer and `durability="sync"`, the agent's service at `UNDERCOVER_AGENT`, the tracing sessions
- [ ] `docs/PROCESS.md`: `npm run dev` starts the backend, the agent's service and the dashboard; `uv run -m backend.seed` reseeds Supabase when `.env` has `DATABASE_URL`; the tests need no network
- [ ] `docs/CODE_STANDARDS.md` 13: the agent's four parts and its supports; the backend reaches the service only through `backend/agent_service.py`
- [ ] `docs/STATUS.md` and `CLAUDE.md` describe what's built, how to seed, run and sign off, and the live trial
- [ ] `npm run check` passes with `.env` in place and with it moved out of the way

## Not in this plan

- Saving the queue agent's own progress. A stopped run is finished by the next one and its claims are carried on, but its conversation and to-do list aren't resumed.
- Clearing old checkpoints.
- Telling a run which claims another process is working.
- Running the agent's service in the cloud.
- Scoring the agent against `data/evals/`.
- Sign-in, real payments and messages to customers.
