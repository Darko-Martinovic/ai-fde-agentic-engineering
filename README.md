# AI FDE: The Forward Deployed Engineer & Agentic AI Architect

> **Thank you, Ed.** This repo is my fork of Ed Donner's [ed-donner/undercover](https://github.com/ed-donner/undercover), the project behind his Udemy course [AI FDE: The Forward Deployed Engineer & Agentic AI Architect](https://www.udemy.com/course/ai-fde-forward-deployed-engineer-agentic-ai-architect/learn/lecture/58544007#questions). The course, the product briefs, the data and the idea of UnderCover are all his, and building it day by day has been the most practical way I have found to learn agentic engineering. If you want the course itself, its labs and Ed's own builds, start at his repo; his curriculum is at [edwarddonner.com/curriculum](https://edwarddonner.com/curriculum).

## UnderCover Agent: the Travel Insurance Platform

![A boarding pass for the course: Week 1 AI Engineer, Week 2 AI Architect, Week 3 AI FDE, carrying the UnderCover Agent to production on AWS](assets/undercover-boarding-pass.svg)

UnderCover is a fictional travel insurer. The course builds its claims platform: a backend that holds the records and enforces the rules, an AI agent that works the claims through the backend's API, and a dashboard where the claims handlers watch it, sign off large payouts and finish the claims it refers.

This README describes what I added on top of Ed's builds. Each day's build here starts from Ed's brief, but on my own code rather than his day branch, and each one is kept on a locked branch:

| Branch | What it is | Compared with |
|---|---|---|
| [`week1day3-end`](https://github.com/Darko-Martinovic/undercover/tree/week1day3-end) | The pilot from `docs/SPEC.md` | Ed's `week1day3-end` |
| [`week1day5-end`](https://github.com/Darko-Martinovic/undercover/tree/week1day5-end) | The harness from `docs/HARNESS.md`, with Insights and the model comparison | Ed's `week1day5-end` |
| `main` | The latest build, where work goes in through PRs | |

## Week 1 Day 3: the pilot

![The queue after a run of the agent](assets/queue-after-run.png)

| | Ed's build | Mine |
|---|---|---|
| Running the agent | Command line | Command line, and Run and Stop in the dashboard. The agent runs as a separate process, one run at a time; Stop ends it at once and puts the claim back to `waiting`, keeping its steps |
| Referrals | A referral is final | A `referred` state and a form where a handler approves or declines the claim |
| Queue | Counts by state and a line per claim | Tiles per state that filter the table, money totals, search, a type filter and sortable columns |
| After a run | Each decision printed, then a count | Insights, below |
| API | 13 operations | 20 at the pilot (30 now), with a Postman collection that runs through the workflow and starts and stops the agent |

**Insights** answers how a whole run went, from the records the pilot already keeps, with one read-only endpoint and no new tables: claims straight through, time per claim, a timeline of the latest run, tool calls with the calls the backend refused, decisions by claim type, the policy sections cited, and the money claimed, paid and held for sign-off. The charts are plain CSS in the brand's colors. The plan is [docs/PLAN_INSIGHTS.md](docs/PLAN_INSIGHTS.md).

![Insights after a run of the queue](assets/insights.png)

## Week 1 Day 5: the harness

![The run panel after five claims on Claude Haiku 5.5](docs/screenshots/harness-run-finished.png)

| | Ed's build | Mine |
|---|---|---|
| Capped runs | `uv run -m agent --cap 5` | The same, and Run 5 and Run all in the dashboard, with the number of claims in a field |
| Model | DeepSeek V4.1 Flash on OpenRouter, or `MODEL_NAME` | Any model in `models.toml`, on OpenRouter, Anthropic or a local Ollama, picked in the dashboard or with `--model`. The running model is shown, never written in code |
| Settings | Defaults in code, such as the backend's URL | `.env.defaults` (committed), `.env` and `models.toml` with prices. No host, port, URL, model id or price in code, and tests that fail if one appears |
| Watching a run | The latest run's to-do list and summary | A live run panel: model, claims done of the cap, time taken and time left at the pace so far, model calls, tokens and cost, the to-do list, and the claim being worked with its steps arriving |
| Usage | Not recorded | Each model call's tokens, cost and time, on the run |
| Agent modules | `api.py`, `tools.py`, `harness.py` | The same three, plus `middleware.py` (the step and usage recorders) and `config.py` (the models allowed) |
| Pages | Queue, claim, instructions | Queue, claim, Insights and instructions |
| Accuracy | Not scored | The model comparison, below |

Both builds took the same decisions on the five longest-waiting claims. The plan is [docs/PLAN_HARNESS.md](docs/PLAN_HARNESS.md).

### The model comparison

`uv run -m bench` runs each trial in `bench/plan.toml` from a fresh database, through the same harness the dashboard uses, and scores every claim against the handlers' own decisions: the decision, and for an approval the payout within a dollar. Only `bench/score.py` reads the answer key in `data/evals/`; the agent and the backend never do, and a test checks it. It refuses to pass a budget (`BENCH_BUDGET_USD`), resumes from the runs it has saved, and tries again a run the provider refused instead of scoring it 0%.

![Accuracy by model](bench/results.svg)

| Model | Claims | Runs | Decision right | Payout right | Cost a claim | Time a claim |
|---|---|---|---|---|---|---|
| Claude Haiku 5.5 | all 25 | 3 | 84% | 80% | $0.0047 | 16 s |
| Claude Opus 5.5 | the 5 tiny | 3 | 93% | 93% | $0.1142 | 21 s |
| Qwen 3.5 4B, local | all 25 | 2 | 54% | 46% | free | 65 s |

The whole comparison cost $2.06. Haiku's steadiest misses are claims the handlers referred and the agent decided, so the referral rules are the next thing to improve. The full report, with every claim each model got wrong, is [bench/results.md](bench/results.md).

## How it's built

- **Standards checked by tests.** Ed's code standards 1 to 14 plus eight more in [docs/CODE_STANDARDS.md](docs/CODE_STANDARDS.md), enforced by `tests/test_standards.py`, `dashboard/src/standards.test.ts`, ESLint and ruff: one owner for each service's address, one name for each operation, all SQL in `backend/store/`, functions under 40 lines and modules under 300, complexity limits, and no configuration in code.
- **Reviewed and merged by PR.** As in Ed's process, a fresh agent reviews every change against the standards before it is committed ([docs/PROCESS.md](docs/PROCESS.md)). On top of that, a pre-commit hook runs every check, each phase goes in through its own PR, and `main` and the day branches are protected.
- **Tests that never call a model.** Agent tests script a stub model and run the real backend in-process. 34 Python and TypeScript test files (Ed's `week1day5-end` has 15), Playwright end-to-end tests on their own ports and database, and a Postman collection for the whole API.

## Running it

Install [uv](https://docs.astral.sh/uv/) and Node, then from the repo root:

```
uv sync
npm install
cp .env.example .env     # add OPENROUTER_API_KEY and/or ANTHROPIC_API_KEY
npm run dev              # backend on 8000, dashboard on http://localhost:5173
```

| Task | Command |
|---|---|
| The queue agent on five claims, on a model from `models.toml` | `uv run -m agent --cap 5 --model anthropic:claude-haiku-5-5` |
| One claim | `uv run -m agent CLM-1001` |
| Reset the data | `uv run -m backend.seed` |
| Every check | `npm run check` |
| End-to-end tests | `npm run e2e` |
| The model comparison (calls the models; `--estimate` prints its cost) | `uv run -m bench` |

A local model needs [Ollama](https://ollama.com) with the model pulled, such as `ollama pull qwen3.5:4b`, and costs nothing. [docs/STATUS.md](docs/STATUS.md) describes everything that is built and every live run.

## Shared with the course

- [PR #11](https://github.com/ed-donner/undercover/pull/11): the pilot and Insights, as `community_contributions/Darko-Martinovic/PILOT.md`
- [PR #24](https://github.com/ed-donner/undercover/pull/24): the harness and the model comparison, as `community_contributions/Darko-Martinovic/HARNESS.md`
