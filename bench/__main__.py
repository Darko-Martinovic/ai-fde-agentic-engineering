"""Run the model comparison in bench/plan.toml against the backend at
UNDERCOVER_API, with the agent's service running (npm run dev) and no dispatch
or evaluation going: each run is an evaluation, as one from the Scoreboard,
which the backend scores. Runs already in bench/results.json are kept, so a
comparison that stops picks up where it was; a run the provider refused is
tried again. It refuses to start, or to go on, when the cost would pass
BENCH_BUDGET_USD."""

import argparse
import sys

from bench.plan import SET_SIZES, Estimate, Trial, load
from bench.report import FOLDER, write_report
from bench.run import RESULTS, Repeat, load_results, run_repeat, save_results, tally
from settings import setting


def parse(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="uv run -m bench", description=__doc__)
    parser.add_argument(
        "--estimate", action="store_true", help="say what it would cost, and stop"
    )
    parser.add_argument(
        "--report", action="store_true", help="write the report from the runs done"
    )
    return parser.parse_args(arguments)


def pending(trials: list[Trial], results: list[Repeat]) -> list[tuple[Trial, int]]:
    """The runs of the plan not done yet, or refused, as a trial and the run's
    number."""
    done = {(r.model, r.claims, r.agents, r.repeat) for r in results if not r.refused}
    return [
        (trial, repeat)
        for trial in trials
        for repeat in range(1, trial.repeats + 1)
        if (trial.model.spec, trial.claims, trial.agents, repeat) not in done
    ]


def expected(trial: Trial, estimate: Estimate) -> float:
    """What one run of a trial should cost."""
    return estimate.cost(trial.model, SET_SIZES[trial.claims])


def replace(results: list[Repeat], result: Repeat) -> list[Repeat]:
    """The runs with this one in place of an earlier, refused try at it, or
    added at the end."""
    same = (result.model, result.claims, result.agents, result.repeat)
    tries = [(r.model, r.claims, r.agents, r.repeat) for r in results]
    if same not in tries:
        return [*results, result]
    return [result if run == same else r for r, run in zip(results, tries, strict=True)]


def check_budget(spent: float, cost: float, budget: float) -> None:
    if spent + cost > budget:
        raise SystemExit(
            f"Refused: ${spent:.2f} spent and ${cost:.2f} more would pass the "
            f"budget of ${budget:.2f} (BENCH_BUDGET_USD)."
        )


def main(arguments: list[str]) -> None:
    """Run what's left of the plan within the budget, then write the report."""
    options = parse(arguments)
    trials, estimate = load()
    results = load_results(RESULTS)
    if options.report:
        write_report(results, FOLDER)
        return
    todo = pending(trials, results)
    budget = float(setting("BENCH_BUDGET_USD"))
    spent = sum(result.cost for result in results)
    total = sum(expected(trial, estimate) for trial, _ in todo)
    print(f"{len(todo)} runs to do, about ${total:.2f}; ${spent:.2f} spent so far.")
    if options.estimate:
        return
    check_budget(spent, total, budget)
    for trial, repeat in todo:
        check_budget(spent, expected(trial, estimate), budget)
        print(f"{trial.model.label}, {trial.claims} claims, run {repeat}", flush=True)
        result = tally(trial, repeat, run_repeat(trial))
        results = replace(results, result)
        save_results(results, RESULTS)
        spent += result.cost
    write_report(results, FOLDER)


if __name__ == "__main__":
    main(sys.argv[1:])
