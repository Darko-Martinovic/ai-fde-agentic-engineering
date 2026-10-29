# Process

`uv sync` and `npm install` at the repo root install everything, including a git pre-commit hook. `npm run dev` starts the backend, the agent's service and the dashboard. `.env` needs `UNDERCOVER_API_KEY`, the agent's key, without which the agent's service won't start. With `DATABASE_URL` in `.env`, the records and the agent's saved progress are on Supabase, and `uv run -m backend.seed` reseeds Supabase. The tests never read `.env` and need no network: they use SQLite and save the agent's progress in memory, sign handlers in with a key made for the test run, stand in a fixed grade for the judge, and run the improver and the claim agents on stub models. The end-to-end tests start stand-ins for the agent's service, Supabase Auth and the judge (`e2e/agent-stand-in.ts`, `auth-stand-in.ts`, `judge-stand-in.ts`), so they reach none of the real ones.

`npm run check` runs every check:

- Python: ruff (lint and format), pyright, pytest with 80% coverage, and the backend imported with the `server` dependency group alone (`npm run check:server`)
- TypeScript: ESLint, Prettier, tsc, and vitest with 80% coverage
- Playwright end-to-end tests

`npm run build` builds the dashboard into `dashboard/dist`, which the backend then serves beside the API; `docs/TECH_STACK.md`'s Deployment section says what goes to AWS Lambda.

The pre-commit hook runs the format, lint, type and unit test checks on every commit.

## Planning

When asked to plan, as in "Please plan the pilot", write the plan to `docs/PLAN.md` and write no code.

- Start with the design: the modules, what each one is for, and how they depend on each other. Check it against `docs/CODE_STANDARDS.md` before you write the phases. Describe the agent's instructions by their goals, never as a list of steps.
- Split the work into phases, usually 5 or 6, each building on the last.
- Give each phase detailed success criteria that you can verify yourself: tests that pass, commands and their output, API calls and their responses, and pages you check in the browser with the Playwright MCP server. Write each one as a checkbox.
- Then stop and wait until you are asked to implement the plan.

## Implementing

When asked to implement the plan, as in "Please implement the plan for the pilot", build every phase in order without stopping. For each phase:

1. Build it, with tests.
2. Check every success criterion and fix whatever fails.
3. Review the phase's changes, as described below, and fix what the review finds.
4. Tick off its criteria in the plan and update `docs/STATUS.md`.
5. Commit. The pre-commit hook runs the checks; if it fails, fix the problem and commit again.

When the last phase is done, review the whole branch against `main` in the same way and fix what the review finds. Then run `npm run check` and report the results, including what the reviews found and what you changed.

## Reviewing

The checks show that the code works, but not that it is fit to merge. Every code change gets a review before it is committed.

- The reviewer is a fresh subagent that didn't write the code. Give it `docs/CODE_STANDARDS.md` and the diff, and ask it to review as a strict senior engineer deciding whether to merge the PR.
- It checks every standard, in particular: one way to call each service, with each URL written once; modules that keep to their own job and don't borrow each other's helpers; the framework's own way of doing things over hand-rolled code; functions that do one job; configuration only from the env files and `data/models.json`; and agent instructions written as goals.
- Fix everything it would block the PR for before you commit. If you disagree with a finding, say so in your report instead of skipping it quietly.

## Rules

- Add tests with each change. Tests never call a model; use a stub model.
- Outside a plan, commit each change once you have checked and reviewed it.
- Run `npm run check` before you hand work over.
- Never use `git commit --no-verify`.
- Runs on a real model: estimate the cost first, reseed once, then start a dispatch or a round of improvement from the dashboard, signed in; evaluations and rounds work copies and need no reseed. Keep to the runs a brief asks for, with `MODEL_NAME` out of `.env`, and report what they spent, from the backend's records and the OpenRouter key's usage. Don't edit `backend/` or `agent/` while a run works: `npm run dev` reloads them, and a reload stops the run.
- Browser checks sign in on the dashboard as one of the handlers in Supabase Auth, with `HANDLER_PASSWORD` from `.env` (Dana Whitfield can sign off over the limit, Marcus Oyelaran can't). API checks get a handler's access token from Supabase Auth's password grant the same way. Never print the password or a token.
- Never lower a threshold, turn off a rule or exclude a file to get a green run. If a rule looks wrong, stop and ask.
- Keep `docs/STATUS.md` up to date.
- Never push.
- Don't open `data/evals/` unless you're asked to.
- Everything must work on Windows: write `package.json` scripts as `uv run` commands or `.mjs` files.
