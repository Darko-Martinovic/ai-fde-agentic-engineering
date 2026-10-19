# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`AGENTS.md` is the main instruction file, and Claude Code loads it on its own: the course context, the required reading in `docs/` before any product work, the build-day workflow and the branch rules. This file adds the commands and the architecture.

## Remotes

`origin` (`Darko-Martinovic/undercover`, a fork of `ed-donner/undercover`) is the only remote; the student removed Ed's repo. `gh` defaults to the fork, so PRs open there. Ed's day branches aren't available locally: if `AGENTS.md` calls for one, or for pulling Ed's updates, ask the student before adding `https://github.com/ed-donner/undercover.git` back as `upstream`. `docs/PROCESS.md` says never push; push only when the student asks.

## Commands

Run from the repo root. Python always goes through `uv run`, never `python`/`python3`.

| Task | Command |
|---|---|
| Install everything, including the lefthook pre-commit hook and Playwright's Chromium | `uv sync` then `npm install` |
| Backend (port 8000) and dashboard (port 5173) | `npm run dev` |
| Every check (what to run before handing work over) | `npm run check` |
| Python checks: ruff format, ruff lint, pyright, pytest with 80% coverage | `npm run check:python` |
| TypeScript checks: prettier, ESLint, tsc, vitest with 80% coverage | `npm run check:ts` |
| End-to-end tests (start their own backend on 8001 and dashboard on 5174 with a fresh `e2e/undercover-e2e.db`; those ports must be free) | `npm run e2e` |
| Format everything | `npm run format` |
| Run the agent on one claim, or on every waiting claim (calls the model) | `uv run -m agent CLM-1001`, `uv run -m agent` |
| Reset the database to `data/` | `uv run -m backend.seed` |
| One Python test | `uv run pytest agent/tests/test_agent.py::test_run --no-cov` |
| One vitest file | `npx vitest run --root dashboard src/App.test.tsx` |
| One Playwright test | `npx playwright test e2e/claims.spec.ts` |
| Postman collection against the dev backend (reset the data first) | `npx -y newman@6 run postman/undercover.postman_collection.json -e postman/undercover_local.postman_environment.json` |

`--no-cov` matters for single Python tests: `pyproject.toml` adds `--cov` with `fail_under = 80`, so a partial run fails on coverage otherwise. pyright is the npm package (`npx pyright`), configured to use `.venv`.

The pre-commit hook runs `check:python` when `backend/` or `agent/` files are staged and `check:ts` when `dashboard/`, `e2e/` or `*.config.*` files are staged. Never bypass it with `--no-verify`, and never lower thresholds or disable lint rules to get a green run (`docs/PROCESS.md`).

## Architecture

The product is three parts that talk only over HTTP, plus e2e tests:

- `backend/main.py`: FastAPI app (`backend.main:app`). Every route under `/api` has an `operation_id`, a one-line docstring and no optional inputs (`docs/TECH_STACK.md`), because the agent's tools are built against this API. SQLite is the store until Week 2 Day 3 moves to Supabase. `backend/workflow.py` holds the claim states and the $1,000 sign-off rule: the backend enforces them, so the agent can't bypass them. `backend/api.py` has what routes share (the per-request database, `load_claim`).
- `agent/main.py`: the UnderCover Agent, LangChain `create_agent` on OpenRouter via `ChatOpenAI` with `base_url` set to OpenRouter. The entry point is `run(claim_id, thread_id, llm=None)`: it starts the claim, builds the system prompt from `GET /api/instructions` plus `GET /api/policy-wording`, streams the agent and posts every tool call, tool result and reply to `record_step`. Each tool is one API call, and a refused call (4xx) comes back to the model as text instead of raising. The agent reaches claims only through the backend API (`backend()` returns an `httpx.Client` on `localhost:8000`), never by reading `data/` or the database directly. The model is `MODEL_NAME` from `.env` if set (for example `openrouter/free`), otherwise `openai/gpt-6-luna` with low reasoning effort. `agent/__main__.py` is the command line.
- `backend/runner.py`: the dashboard's Run and Stop. It starts `agent.__main__.main` in a separate process (multiprocessing, spawn), one run at a time, and Stop terminates that process and puts any `in_progress` claim back to `waiting`, clearing its unpaid decision. Tests replace `start_process` with a fake, so no model is called.
- `dashboard/`: React + Vite + TypeScript (strict, no `any`). Vite proxies `/api` to `127.0.0.1:8000`, so the dashboard calls relative `/api/...` URLs. Pages are routed by the URL hash (`useRoute` in `hooks.ts`), data is loaded with `usePoll` (refreshes on an interval, pauses when the tab is hidden), and every API call goes through `api.ts`. Brand tokens and the light and dark themes are CSS variables in `styles.css`. Tests stub `fetch` with `mockFetch` from `testing.ts`, keyed by `"METHOD /path"`. ESLint is strict: props are `Readonly<>`, no nested ternaries, no numbers in template strings without `String()`.
- `e2e/`: Playwright on its own ports and database (`playwright.config.ts`; the dashboard's proxy target comes from `UNDERCOVER_API`). Tests set up the agent's decisions through the API, so no model is called.
- `postman/`: the API's Postman collection and environment. Add every new or changed endpoint to the collection.

Testing pattern for the agent (see `agent/tests/test_agent.py`): tests never call a real model. They pass a `StubModel` (a `GenericFakeChatModel` whose `bind_tools` returns itself) with scripted `AIMessage`s, including tool calls, as `llm`, and monkeypatch `main.backend` to return FastAPI's `TestClient(app)` so the agent's tools hit the real backend in-process.

Data: `data/` is the business data the backend seeds from. `data/evals/` is the answer key: the agent must never see it, and don't open it unless asked. `context/` holds data governance's files, which become the context layer on Week 3 Day 3.

`docs/STATUS.md` describes what is built and how to run it; keep it current as the build grows, since the skeleton above is replaced build by build.
