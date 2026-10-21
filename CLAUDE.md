# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`AGENTS.md` is the main instruction file, and Claude Code loads it on its own: the course context, the required reading in `docs/` before any product work, the build-day workflow and the branch rules. This file adds the commands and the architecture.

## Remotes

`origin` is the student's fork (`Darko-Martinovic/undercover`) and `upstream` is Ed's repo (`ed-donner/undercover`), so Ed's day branches are `upstream/<branch>` after `git fetch upstream`. `gh` defaults to the fork, so PRs open there; a contribution to Ed's repo goes through `community_contributions/` as `guides/for_agents/AGENT_GIT_GUIDE.md` describes, with `gh pr create --repo ed-donner/undercover`. `docs/PROCESS.md` says never push; push only when the student asks.

## Commands

Run from the repo root. Python always goes through `uv run`, never `python`/`python3`.

| Task | Command |
|---|---|
| Install everything, including the lefthook pre-commit hook and Playwright's Chromium | `uv sync` then `npm install` |
| Backend and dashboard, on the ports in `.env.defaults` (8000 and 5173) | `npm run dev` (the backend alone: `uv run -m backend`) |
| Every check (what to run before handing work over) | `npm run check` |
| Python checks: ruff format, ruff lint, pyright, pytest with 80% coverage | `npm run check:python` |
| TypeScript checks: prettier, ESLint, tsc, vitest with 80% coverage | `npm run check:ts` |
| End-to-end tests (start their own backend on 8001 and dashboard on 5174 with a fresh `e2e/undercover-e2e.db`; those ports must be free) | `npm run e2e` |
| Format everything | `npm run format` |
| Run the agent on one claim, or on every waiting claim (calls the model) | `uv run -m agent CLM-1001`, `uv run -m agent` |
| Reset the database to `data/` | `uv run -m backend.seed` |
| One Python test | `uv run pytest agent/tests/test_harness.py::test_work_claim_approves_and_pays --no-cov` |
| One vitest file | `npx vitest run --root dashboard src/App.test.tsx` |
| One Playwright test | `npx playwright test e2e/claims.spec.ts` |
| Postman collection against the dev backend (reset the data first) | `npx -y newman@6 run postman/undercover.postman_collection.json -e postman/undercover_local.postman_environment.json` |

`--no-cov` matters for single Python tests: `pyproject.toml` adds `--cov` with `fail_under = 80`, so a partial run fails on coverage otherwise. pyright is the npm package (`npx pyright`), configured to use `.venv`.

The pre-commit hook runs `check:python` when Python files (`backend/`, `agent/`, `tests/`), `*.toml` or `.env.defaults` are staged and `check:ts` when `dashboard/`, `e2e/`, `*.config.*` or `.env.defaults` files are staged. Never bypass it with `--no-verify`, and never lower thresholds or disable lint rules to get a green run (`docs/PROCESS.md`).

## Architecture

The product is three parts that talk only over HTTP, plus e2e tests:

- `backend/`: FastAPI app (`backend.main:app`), run with `uv run -m backend`. Every route under `/api` has an `operation_id`, a one-line docstring and no optional inputs (`docs/TECH_STACK.md`), because the agent's tools are built against this API. SQLite is the store until Week 2 Day 3 moves to Supabase. `backend/workflow.py` holds the claim states and the $1,000 sign-off rule: the backend enforces them, so the agent can't bypass them. `backend/api.py` has what routes share (the per-request database, `load_claim`). `main.py` only puts the app together from one router per resource: `claims.py`, `records.py`, `documents.py`, `workflow.py`, `runner.py` and `insights.py`. All SQL is in `backend/store/` (`claims.py`, `records.py`, `steps.py`); `db.py` holds the schema.
- `agent/`: the UnderCover Agent, LangChain `create_agent`, in four modules (`docs/CODE_STANDARDS.md` 13). `api.py` is the only way to the backend: one function per operation, named after it, at `UNDERCOVER_API`; a 4xx raises `api.Refused`. `tools.py` holds the tools; a claim agent's tools read the claim from `ToolRuntime[ClaimContext]`. `harness.py` builds the model with `init_chat_model` from `MODEL_NAME` (`openrouter:`, `anthropic:` or `ollama:`, one of those in `models.toml`), records every reply, tool call and tool result with the `StepRecorder` middleware, turns `Refused` into text for the model with `ToolErrorMiddleware`, and runs a claim with `work_claim(claim_id, llm=None)`. `config.py` reads `models.toml`; settings come from the root `settings.py`. `agent/__main__.py` is the command line.
- `backend/runner.py`: the dashboard's Run and Stop. It starts `agent.__main__.main` in a separate process (multiprocessing, spawn), one run at a time, and Stop terminates that process and puts any `in_progress` claim back to `waiting`, clearing its unpaid decision. Tests replace `start_process` with a fake, so no model is called.
- `dashboard/`: React + Vite + TypeScript (strict, no `any`). The keys of `api` in `api.ts` are the backend's operation ids in camelCase. Vite proxies `/api` to `UNDERCOVER_API`, so the dashboard calls relative `/api/...` URLs. Pages are routed by the URL hash (links and `parseRoute` in `paths.ts`, `useRoute` in `hooks.ts`), data is loaded with `usePoll` (refreshes on an interval, pauses when the tab is hidden), and every API call goes through `api.ts`. Brand tokens and the light and dark themes are CSS variables in `styles.css`. Tests stub `fetch` with `mockFetch` from `testing.ts`, keyed by `"METHOD /path"`. ESLint is strict: props are `Readonly<>`, no nested ternaries, no numbers in template strings without `String()`.
- `e2e/`: Playwright on its own ports and database (`playwright.config.ts`; the dashboard's proxy target comes from `UNDERCOVER_API`). Tests set up the agent's decisions through the API, so no model is called.
- `postman/`: the API's Postman collection and environment. Add every new or changed endpoint to the collection.

Configuration (`docs/CODE_STANDARDS.md` 22): `settings.py` (Python) and `settings.config.ts` (TypeScript) load the env files. `.env.defaults` (committed) holds every setting that isn't secret, with `${NAME}` for values built from others, `.env` the keys and overrides, and `models.toml` the models allowed with prices. No host, port, URL, model id or price is written in code; `tests/test_standards.py` and `dashboard/src/standards.test.ts` fail if one is. The root `conftest.py` makes tests read `.env.defaults` alone, and so does the e2e run.

Testing pattern for the agent (see `agent/tests/test_harness.py`): tests never call a real model. They pass a `StubModel` (a `GenericFakeChatModel` whose `bind_tools` returns itself) with scripted `AIMessage`s, including tool calls, as `llm`, and the autouse fixture in `agent/tests/conftest.py` monkeypatches `api.client` to return FastAPI's `TestClient(app)` so the agent's tools hit the real backend in-process.

Data: `data/` is the business data the backend seeds from. `data/evals/` is the answer key: the agent must never see it, and don't open it unless asked. `context/` holds data governance's files, which become the context layer on Week 3 Day 3.

`docs/STATUS.md` describes what is built and how to run it; keep it current as the build grows, since the skeleton above is replaced build by build.
