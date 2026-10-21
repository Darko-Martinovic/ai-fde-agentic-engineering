"""A comparison run end to end on stub models, scored against hand-made answers."""

import pytest
from langchain_core.messages import AIMessage

import bench.__main__ as cli
from agent import harness
from agent.config import Model
from agent.tests.stub import FREE, decide, stub, tool_call
from bench.plan import Estimate, Trial
from bench.report import write_report
from bench.run import Repeat, load_results, run_repeat, save_results

# CLM-1001 approved and paid as the handlers did; CLM-1005 approved, where they
# declined it
SCRIPTS = [
    [decide("approve", 420), tool_call("pay_claim", amount=420), AIMessage("Paid.")],
    [decide("approve", 243), tool_call("pay_claim", amount=243), AIMessage("Paid.")],
]


@pytest.fixture
def models(monkeypatch):
    """Give each claim agent, in turn, a stub model with the next script."""
    scripts = iter(SCRIPTS)
    monkeypatch.setattr(harness, "chat_model", lambda model: stub(*next(scripts)))


def test_a_run_is_scored_against_the_answers(key, models):
    result = run_repeat(Trial(FREE, "tiny", 1), 1, key)
    assert (result.worked, result.decisions_right, result.payouts_right) == (2, 1, 1)
    assert result.undecided == 0
    assert result.model_calls == 6
    assert result.misses == [
        {
            "claim_id": "CLM-1005",
            "expected": "decline",
            "expected_payout": 0.0,
            "got": "approve",
            "got_payout": 243.0,
            "status": "decided",
        }
    ]


def test_results_are_kept_between_runs(tmp_path, key, models):
    result = run_repeat(Trial(FREE, "tiny", 1), 1, key)
    save_results([result], tmp_path / "results.json")
    assert load_results(tmp_path / "results.json") == [result]
    assert load_results(tmp_path / "missing.json") == []


@pytest.fixture
def plan(tmp_path, monkeypatch, key):
    """A plan of one tiny trial, two runs, kept in a folder of its own."""
    monkeypatch.setattr(cli, "load", lambda: ([Trial(FREE, "tiny", 2)], ESTIMATE))
    monkeypatch.setattr(cli, "answers", lambda: key)
    monkeypatch.setattr(cli, "RESULTS", tmp_path / "results.json")
    monkeypatch.setattr(cli, "FOLDER", tmp_path)
    return tmp_path


ESTIMATE = Estimate(input_tokens=63000, output_tokens=3400)


def test_the_comparison_runs_the_plan_and_writes_the_report(plan, monkeypatch):
    monkeypatch.setattr(harness, "chat_model", lambda model: stub(*SCRIPTS[0]))
    cli.main([])
    results = load_results(plan / "results.json")
    assert [r.repeat for r in results] == [1, 2]
    assert "| OpenRouter free router | tiny (2) | 2 |" in (
        plan / "results.md"
    ).read_text(encoding="utf-8")
    assert "OpenRouter free router" in (plan / "results.svg").read_text(
        encoding="utf-8"
    )
    cli.main([])
    assert len(load_results(plan / "results.json")) == 2


def test_the_comparison_refuses_to_pass_its_budget(plan, monkeypatch, capsys):
    priced = Model(FREE.spec, "Priced", 1.0, 1.0, {})
    paid = Trial(priced, "tiny", 1)
    monkeypatch.setattr(cli, "load", lambda: ([paid], ESTIMATE))
    monkeypatch.setenv("BENCH_BUDGET_USD", "0.01")
    with pytest.raises(SystemExit, match="would pass the budget of \\$0.01"):
        cli.main([])
    cli.main(["--estimate"])
    assert capsys.readouterr().out.startswith("1 runs to do, about $0.")
    assert not (plan / "results.json").exists()


def test_the_report_alone(plan):
    cli.main(["--report"])
    assert (
        (plan / "results.md")
        .read_text(encoding="utf-8")
        .startswith("# Model comparison")
    )


def repeat(model_calls: int) -> Repeat:
    """A tiny run of the free router, as saved, with this many model calls."""
    return Repeat(
        FREE.spec, FREE.label, "tiny", 1, 5, 0, 0, 5, model_calls, 0, 0, 0.0, 9.0, []
    )


def test_a_refused_run_is_tried_again_and_not_scored(tmp_path):
    refused, answered = repeat(0), repeat(12)
    assert refused.refused
    assert not answered.refused
    trial = Trial(FREE, "tiny", 1)
    assert cli.pending([trial], [refused]) == [(trial, 1)]
    assert cli.pending([trial], [answered]) == []
    assert cli.replace([refused], answered) == [answered]
    write_report([refused], tmp_path)
    text = (tmp_path / "results.md").read_text(encoding="utf-8")
    assert "- OpenRouter free router, tiny claims: 1 of 1 runs refused" in text
    assert "| OpenRouter free router |" not in text
