import pytest
from langchain_core.messages import AIMessage

import agent.__main__ as cli
from agent import harness
from agent.tests.stub import StubModel
from backend.tests.direct_changes import set_status


def reply_only(monkeypatch):
    """Give every claim agent a stub model that reads the claim and replies,
    deciding nothing, so each claim fails and goes back in the queue."""

    def stub(model):
        return StubModel(
            messages=iter(
                [
                    AIMessage(
                        content="",
                        tool_calls=[{"name": "get_claim", "args": {}, "id": "1"}],
                    ),
                    AIMessage(content="Looked at it."),
                ]
            )
        )

    monkeypatch.setattr(harness, "chat_model", stub)


def queue_runs(monkeypatch):
    """Stand in for the queue agent, recording how it was started."""
    started = []

    def run_queue(cap, model, saver):
        started.append((cap, model.spec))
        return "Worked the queue."

    monkeypatch.setattr(cli, "run_queue", run_queue)
    return started


def test_one_claim(backend, monkeypatch, capsys):
    reply_only(monkeypatch)
    cli.main(["CLM-1001"])
    expected = f"CLM-1001: failed, back in the queue ({harness.STOPPED})"
    assert capsys.readouterr().out == expected + "\n"
    run = backend.get("/api/runs/latest").json()
    assert (run["mode"], run["cap"], run["status"]) == ("claim", 1, "finished")
    assert run["summary"] == expected


def test_claims_on_a_model(backend, monkeypatch):
    reply_only(monkeypatch)
    cli.main(["CLM-1001", "CLM-1002", "--model", "ollama:qwen3.5:9b"])
    run = backend.get("/api/runs/latest").json()
    assert (run["cap"], run["model"]) == (2, "ollama:qwen3.5:9b")
    assert run["claims_started"] == ["CLM-1001", "CLM-1002"]


def test_the_queue_with_a_cap(backend, monkeypatch, capsys):
    started = queue_runs(monkeypatch)
    cli.main(["--cap", "5", "--model", "anthropic:claude-haiku-5-5"])
    assert started == [(5, "anthropic:claude-haiku-5-5")]
    assert capsys.readouterr().out == "Worked the queue.\n"


def test_the_queue_without_a_cap_takes_every_waiting_claim(backend, monkeypatch):
    started = queue_runs(monkeypatch)
    cli.main([])
    assert started == [(25, "openrouter:deepseek/deepseek-v4.1-flash")]


def test_nothing_waiting(backend, monkeypatch, capsys):
    started = queue_runs(monkeypatch)
    backend.get("/api/claims")
    set_status("decided")
    cli.main([])
    assert started == []
    assert capsys.readouterr().out == "No claims are waiting.\n"


@pytest.mark.parametrize("cap", ["0", "-1", "two"])
def test_a_cap_must_be_one_or_more(backend, monkeypatch, cap):
    started = queue_runs(monkeypatch)
    with pytest.raises(SystemExit):
        cli.main(["--cap", cap])
    assert started == []


def test_a_claim_that_is_not_waiting_is_reported_and_the_run_finished(
    backend, monkeypatch, capsys
):
    reply_only(monkeypatch)
    set_status("decided", "CLM-1001")
    cli.main(["CLM-1001"])
    assert capsys.readouterr().out.startswith("CLM-1001: ")
    assert backend.get("/api/runs/latest").json()["status"] == "finished"
