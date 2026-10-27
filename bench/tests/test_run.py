"""A comparison run end to end: each run an evaluation through the backend and
the agent's service, in process, on stub models."""

import dataclasses

import pytest
from langchain_core.messages import AIMessage

import bench.__main__ as cli
from agent import api, harness
from agent.config import Model
from agent.tests.stub import FREE, ByClaim, decide
from backend import agent_service
from bench import run
from bench.plan import Estimate, Trial
from bench.report import write_report
from bench.run import Repeat, load_results, run_repeat, save_results, tally

TRIAL = Trial(FREE, "tiny", 1, 5)
# The evaluation set's tiny claims, as the stub works their copies: CLM-1015
# approved where the handlers declined it, the rest as they decided
DECISIONS = {
    "CLM-1007": decide("approve", 50.0),
    "CLM-1015": decide("approve", 300.0),
    "CLM-1017": decide("refer", 0),
    "CLM-1020": decide("approve", 240.0),
    "CLM-1021": decide("approve", 825.0),
}


@pytest.fixture
def models(monkeypatch):
    """Claim agents that work each evaluation's copies as DECISIONS says."""

    def model(chosen):
        scripts = {}
        for number in range(1, 10):
            for claim_id, reply in DECISIONS.items():
                scripts[f"{claim_id}-E{number}"] = iter([reply])
        return ByClaim(messages=iter([]), scripts=scripts)

    monkeypatch.setattr(harness, "chat_model", model)


def test_a_run_is_an_evaluation_the_backend_scores(models):
    result = tally(TRIAL, 1, run_repeat(TRIAL))
    assert (result.worked, result.decisions_right, result.payouts_right) == (5, 4, 4)
    assert result.undecided == 0
    assert result.model_calls == 5
    assert result.misses == [
        {
            "claim_id": "CLM-1015",
            "expected": "decline",
            "expected_payout": 0.0,
            "got": "approve",
            "got_payout": 300.0,
            "status": "decided",
        }
    ]


def test_results_are_kept_between_runs(tmp_path, models):
    result = tally(TRIAL, 1, run_repeat(TRIAL))
    save_results([result], tmp_path / "results.json")
    assert load_results(tmp_path / "results.json") == [result]
    assert load_results(tmp_path / "missing.json") == []


@pytest.fixture
def plan(tmp_path, monkeypatch):
    """A plan of one tiny trial, two runs, kept in a folder of its own."""
    two = dataclasses.replace(TRIAL, repeats=2)
    monkeypatch.setattr(cli, "load", lambda: ([two], ESTIMATE))
    monkeypatch.setattr(cli, "RESULTS", tmp_path / "results.json")
    monkeypatch.setattr(cli, "FOLDER", tmp_path)
    return tmp_path


ESTIMATE = Estimate(input_tokens=63000, output_tokens=3400)


def test_the_comparison_runs_the_plan_and_writes_the_report(plan, models):
    cli.main([])
    results = load_results(plan / "results.json")
    assert [r.repeat for r in results] == [1, 2]
    assert "| OpenRouter free router | tiny (5) | 2 |" in (
        plan / "results.md"
    ).read_text(encoding="utf-8")
    assert "OpenRouter free router" in (plan / "results.svg").read_text(
        encoding="utf-8"
    )
    cli.main([])
    assert len(load_results(plan / "results.json")) == 2


def test_the_comparison_refuses_to_pass_its_budget(plan, monkeypatch, capsys):
    priced = Model(FREE.spec, "Priced", 1.0, 1.0, {})
    paid = Trial(priced, "tiny", 1, 5)
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
        FREE.spec, FREE.label, "tiny", 1, 5, 0, 0, 5, model_calls, 0, 0, 0.0, 9.0, [], 5
    )


def test_a_refused_run_is_tried_again_and_not_scored(tmp_path):
    refused, answered = repeat(0), repeat(12)
    assert refused.refused
    assert not answered.refused
    assert cli.pending([TRIAL], [refused]) == [(TRIAL, 1)]
    assert cli.pending([TRIAL], [answered]) == []
    second = dataclasses.replace(answered, repeat=2)
    assert cli.replace([refused, second], answered) == [answered, second]
    assert cli.replace([answered], second) == [answered, second]
    write_report([refused], tmp_path)
    text = (tmp_path / "results.md").read_text(encoding="utf-8")
    assert "- OpenRouter free router, tiny claims: 1 of 1 runs refused" in text
    assert "| OpenRouter free router |" not in text


def test_an_undecided_claim_the_handlers_referred_counts_as_right(monkeypatch):
    """The backend counts a claim the agent didn't decide as a referral."""
    undecided = {**DECISIONS, "CLM-1017": AIMessage(content="Hmm.")}

    def model(chosen):
        scripts = {f"{c}-E1": iter([r, r]) for c, r in undecided.items()}
        return ByClaim(messages=iter([]), scripts=scripts)

    monkeypatch.setattr(harness, "chat_model", model)
    result = tally(TRIAL, 1, run_repeat(TRIAL))
    assert result.undecided == 1
    assert (result.decisions_right, result.payouts_right) == (4, 4)
    assert result.agents == 5


def test_an_evaluation_that_stops_or_never_starts_isnt_a_run(monkeypatch):
    monkeypatch.setattr(run, "POLL_SECONDS", 0)
    monkeypatch.setattr(run, "APPEAR_SECONDS", 0)
    monkeypatch.setattr(
        agent_service,
        "start_evaluation",
        lambda *args: {"agents": 5, "model": FREE.spec},
    )
    with pytest.raises(RuntimeError, match="didn't start the evaluation"):
        run_repeat(TRIAL)
    stopped = api.create_evaluation("evaluation", True, 5, FREE.spec, "none")
    api.finish_run(stopped["run_id"], True)
    with pytest.raises(RuntimeError, match="stopped before it finished"):
        run.finished(stopped["run_id"])
