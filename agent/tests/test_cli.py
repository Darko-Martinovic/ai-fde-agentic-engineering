import pytest
from langchain_core.messages import AIMessage

import agent.__main__ as cli
from agent import harness
from agent.tests.stub import StubModel, decide, stub, tool_call
from backend.tests.direct_changes import set_status
from backend.tests.usage_rows import model_calls, work_times


def models(monkeypatch, *replies):
    """Give every claim agent a stub model with these replies, recording the
    model it was built for."""
    built = []

    def model(chosen):
        built.append(chosen.spec)
        return stub(*replies)

    monkeypatch.setattr(harness, "chat_model", model)
    return built


def test_one_claim_is_worked_outside_any_run(backend, monkeypatch, capsys):
    models(monkeypatch, tool_call("get_claim"), decide("approve", 420.0))
    cli.main(["CLM-1001"])
    assert capsys.readouterr().out == "CLM-1001: approved $420.00, paid\n"
    claim = backend.get("/api/claims/CLM-1001").json()
    assert (claim["run_id"], claim["attempts"]) == (None, 1)
    assert {c["run_id"] for c in model_calls("CLM-1001")} == {None}
    assert [s["run_id"] for s in work_times("CLM-1001")] == [None]
    assert backend.get("/api/dispatches/latest").json() is None


def test_a_model_from_models_toml(backend, monkeypatch):
    built = models(monkeypatch, decide("decline", 0))
    cli.main(["CLM-1005", "--model", "ollama:qwen3.5:9b"])
    assert built == ["ollama:qwen3.5:9b"]


def test_the_default_model_is_model_name(backend, monkeypatch):
    built = models(monkeypatch, decide("decline", 0))
    cli.main(["CLM-1005"])
    assert built == ["openrouter:openai/gpt-6-luna"]


def test_a_claim_in_progress_is_carried_on(backend, monkeypatch, capsys):
    class Stops(StubModel):
        def _generate(self, *args, **kwargs):
            try:
                return super()._generate(*args, **kwargs)
            except (StopIteration, RuntimeError) as exhausted:
                raise KeyboardInterrupt from exhausted

    monkeypatch.setattr(
        harness,
        "chat_model",
        lambda chosen: Stops(messages=iter([tool_call("get_claim")])),
    )
    with pytest.raises(KeyboardInterrupt):
        cli.main(["CLM-1001"])
    thread_id = backend.get("/api/claims/CLM-1001").json()["thread_id"]
    models(monkeypatch, decide("approve", 420.0))
    capsys.readouterr()
    cli.main(["CLM-1001"])
    claim = backend.get("/api/claims/CLM-1001").json()
    assert (claim["thread_id"], claim["attempts"]) == (thread_id, 1)
    assert capsys.readouterr().out == "CLM-1001: approved $420.00, paid\n"


def test_a_claim_needs_naming():
    with pytest.raises(SystemExit):
        cli.main([])


def test_a_claim_that_is_not_waiting_is_reported(backend, monkeypatch, capsys):
    models(monkeypatch, AIMessage(content="Never asked."))
    set_status("decided", "CLM-1001")
    cli.main(["CLM-1001"])
    assert capsys.readouterr().out == (
        "CLM-1001: Claim CLM-1001 is decided, not waiting\n"
    )
