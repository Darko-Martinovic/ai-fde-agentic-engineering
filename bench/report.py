"""The comparison's write-up: bench/results.md, with a table for each trial,
the claims each model got wrong, and a chart in bench/results.svg."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from bench.chart import chart
from bench.run import Repeat

FOLDER = Path(__file__).parent


@dataclass(frozen=True)
class Summary:
    """A trial's runs, added up: accuracy as percentages of the claims, and
    usage per claim."""

    label: str
    claims: str
    runs: int
    worked: int
    decisions: list[float]
    payouts: list[float]
    undecided: int
    model_calls: float
    input_tokens: float
    output_tokens: float
    cost: float
    seconds: float
    misses: list[str]


def percent(part: int, whole: int) -> float:
    return 100 * part / whole if whole else 0.0


def missed_claims(runs: list[Repeat]) -> list[str]:
    """Each claim a trial got wrong, how often, what the handlers decided and
    what the agent did most often."""
    counts: Counter[str] = Counter()
    what: dict[str, list[str]] = defaultdict(list)
    expected: dict[str, str] = {}
    for run in runs:
        for miss in run.misses:
            claim = miss["claim_id"]
            counts[claim] += 1
            expected[claim] = f"{miss['expected']} ${miss['expected_payout']:,.2f}"
            got = miss["got"] or miss["status"]
            what[claim].append(f"{got} ${miss['got_payout'] or 0:,.2f}")
    return [
        f"{claim} ({times} of {len(runs)}): handlers {expected[claim]}, agent "
        f"{Counter(what[claim]).most_common(1)[0][0]}"
        for claim, times in sorted(counts.items())
    ]


def trials(results: list[Repeat]) -> dict[tuple[str, str], list[Repeat]]:
    """Each trial's runs, by model and claims, in the order the trials were run."""
    grouped: dict[tuple[str, str], list[Repeat]] = defaultdict(list)
    for result in results:
        grouped[(result.label, result.claims)].append(result)
    return grouped


def summarize(results: list[Repeat]) -> list[Summary]:
    """Add up each trial's scored runs, leaving out the runs refused."""
    scored = [result for result in results if not result.refused]
    return [
        summary(label, claims, runs) for (label, claims), runs in trials(scored).items()
    ]


def refusals(results: list[Repeat]) -> str:
    """The trials with runs the provider refused, which aren't scored."""
    lines = [
        f"- {label}, {claims} claims: {sum(r.refused for r in runs)} of "
        f"{len(runs)} runs refused"
        for (label, claims), runs in trials(results).items()
        if any(r.refused for r in runs)
    ]
    return "\n".join(lines) + "\n" if lines else "- None\n"


def summary(label: str, claims: str, runs: list[Repeat]) -> Summary:
    worked = sum(run.worked for run in runs)
    return Summary(
        label=label,
        claims=claims,
        runs=len(runs),
        worked=runs[0].worked,
        decisions=[percent(run.decisions_right, run.worked) for run in runs],
        payouts=[percent(run.payouts_right, run.worked) for run in runs],
        undecided=sum(run.undecided for run in runs),
        model_calls=sum(run.model_calls for run in runs) / worked,
        input_tokens=sum(run.input_tokens for run in runs) / worked,
        output_tokens=sum(run.output_tokens for run in runs) / worked,
        cost=sum(run.cost for run in runs) / worked,
        seconds=sum(run.seconds for run in runs) / worked,
        misses=missed_claims(runs),
    )


def spread(values: list[float]) -> str:
    """A mean, with the range when the runs differ."""
    low, high = min(values), max(values)
    if low == high:
        return f"{mean(values):.0f}%"
    return f"{mean(values):.0f}% ({low:.0f}–{high:.0f})"


def table(summaries: list[Summary]) -> str:
    head = (
        "| Model | Claims | Runs | Decision right | Payout right | Undecided "
        "| Model calls | Tokens in / out | Cost | Time |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
    )
    rows = [
        f"| {s.label} | {s.claims} ({s.worked}) | {s.runs} | {spread(s.decisions)} "
        f"| {spread(s.payouts)} | {s.undecided} | {s.model_calls:.1f} "
        f"| {s.input_tokens:,.0f} / {s.output_tokens:,.0f} | ${s.cost:.4f} "
        f"| {s.seconds:.0f} s |"
        for s in summaries
    ]
    return head + "\n".join(rows) + "\n"


def misses(summaries: list[Summary]) -> str:
    parts = []
    for s in summaries:
        lines = "\n".join(f"- {line}" for line in s.misses) or "- None"
        parts.append(f"### {s.label}, {s.claims} claims\n\n{lines}\n")
    return "\n".join(parts)


INTRO = """# Model comparison

Each run reseeds the database and works the claims through the harness, one
claim agent per claim, then reads each claim's decision and payout and the run's
usage through the API. A decision is right when it matches the handlers' in
`data/evals/decisions.json`; a payout is right when the decision is right and,
for an approval, the payout is within a dollar of theirs. A claim left
undecided counts as wrong. Model calls, tokens, cost and time are per claim;
the cost is at the prices in `models.toml`, and the local models cost nothing.
Percentages are the mean of the runs, with their range when they differ. A run
in which the provider answered no model call at all, as when a free model is
rate-limited, says nothing about the model: it isn't scored, it is listed under
"Runs refused", and the next `uv run -m bench` tries it again.

![Accuracy by model](results.svg)

"""


def write_report(results: list[Repeat], folder: Path) -> None:
    """Write results.md and results.svg from the runs."""
    summaries = summarize(results)
    text = (
        INTRO
        + table(summaries)
        + "\n## The claims each model got wrong\n\n"
        + misses(summaries)
        + "\n## Runs refused\n\n"
        + refusals(results)
    )
    (folder / "results.md").write_text(text, encoding="utf-8")
    (folder / "results.svg").write_text(chart(summaries), encoding="utf-8")
