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
| End-to-end tests (starts backend and dashboard itself, or reuses running ones) | `npm run e2e` |
| Format everything | `npm run format` |
| One Python test | `uv run pytest agent/tests/test_agent.py::test_run --no-cov` |
| One vitest file | `npx vitest run --root dashboard src/App.test.tsx` |
| One Playwright test | `npx playwright test e2e/health.spec.ts` |

`--no-cov` matters for single Python tests: `pyproject.toml` adds `--cov` with `fail_under = 80`, so a partial run fails on coverage otherwise. pyright is the npm package (`npx pyright`), configured to use `.venv`.

The pre-commit hook runs `check:python` when `backend/` or `agent/` files are staged and `check:ts` when `dashboard/`, `e2e/` or `*.config.*` files are staged. Never bypass it with `--no-verify`, and never lower thresholds or disable lint rules to get a green run (`docs/PROCESS.md`).

## Architecture

The product is three parts that talk only over HTTP, plus e2e tests:

- `backend/main.py`: FastAPI app (`backend.main:app`). Every route under `/api` has an `operation_id`, a one-line docstring and no optional inputs (`docs/TECH_STACK.md`), because the agent's tools are built against this API. SQLite is the store until Week 2 Day 3 moves to Supabase. `backend/workflow.py` holds the claim states and the $1,000 sign-off rule: the backend enforces them, so the agent can't bypass them. `backend/api.py` has what routes share (the per-request database, `load_claim`).
- `agent/main.py`: the UnderCover Agent, LangChain `create_agent` on OpenRouter via `ChatOpenAI` with `base_url` set to OpenRouter. The single entry point is `run(claim_id, thread_id, llm=None)`. The agent reaches claims and its instructions only through the backend API (`backend()` returns an `httpx.Client` on `localhost:8000`), never by reading `data/` or the database directly. The model is `MODEL_NAME` from `.env` if set (for example `openrouter/free`), otherwise `openai/gpt-6-luna` with low reasoning effort.
- `dashboard/`: React + Vite + TypeScript (strict, no `any`). Vite proxies `/api` to `127.0.0.1:8000`, so the dashboard calls relative `/api/...` URLs.
- `e2e/`: Playwright against `localhost:5173`; `playwright.config.ts` launches both servers.

Testing pattern for the agent (see `agent/tests/test_agent.py`): tests never call a real model. They pass a `StubModel` (a `GenericFakeChatModel` whose `bind_tools` returns itself) with scripted `AIMessage`s, including tool calls, as `llm`, and monkeypatch `main.backend` to return FastAPI's `TestClient(app)` so the agent's tools hit the real backend in-process.

Data: `data/` is the business data the backend seeds from. `data/evals/` is the answer key: the agent must never see it, and don't open it unless asked. `context/` holds data governance's files, which become the context layer on Week 3 Day 3.

`docs/STATUS.md` describes what is built and how to run it; keep it current as the build grows, since the skeleton above is replaced build by build.
