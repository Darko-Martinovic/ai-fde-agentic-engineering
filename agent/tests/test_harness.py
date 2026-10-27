import json
from time import monotonic

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from agent import harness
from agent.config import model
from agent.tests.stub import FREE, REASONS, StubModel, decide, stub, tool_call
from agent.tools import CLAIM_TOOLS
from backend.tests.usage_rows import model_calls, work_times


def test_work_claim_approves_and_the_graph_pays(backend, run, memory_saver):
    llm = stub(
        tool_call("get_claim"),
        tool_call("get_policy", policy_id="POL-2001"),
        tool_call("get_customer", customer_id="CUS-3001"),
        decide("approve", 420.0),
    )
    report = harness.work_claim("CLM-1001", run, FREE, memory_saver, llm)
    assert report == "CLM-1001: approved $420.00, paid"
    claim = backend.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 420.0
    steps = backend.get("/api/claims/CLM-1001/steps").json()
    assert [s["kind"] for s in steps] == ["tool_call", "tool_result"] * 4
    assert not any(s["text"].startswith("pay_claim") for s in steps)
    assert backend.get("/api/dispatches/latest").json()["usage"]["model_calls"] == 4
    assert steps[0]["text"] == "get_claim {}"
    assert '"story"' in steps[1]["text"]
    assert len({s["thread_id"] for s in steps}) == 1
    assert steps[0]["thread_id"].startswith("CLM-1001-")


def test_a_tool_cannot_reach_another_claim(backend, run, memory_saver):
    """The claim comes from the run's context: a claim the model names is ignored."""
    elsewhere = tool_call(
        "decide_claim",
        claim_id="CLM-1001",
        decision="decline",
        payout=0,
        reasons="Trying another claim.",
        policy_section="Policy wording 9, General exclusions",
    )
    harness.work_claim(
        "CLM-1003",
        run,
        FREE,
        memory_saver,
        stub(elsewhere),
    )
    assert backend.get("/api/claims/CLM-1003").json()["status"] == "decided"
    assert backend.get("/api/claims/CLM-1001").json()["status"] == "waiting"
    for claim_tool in CLAIM_TOOLS:
        model_sees = convert_to_openai_tool(claim_tool)["function"]["parameters"]
        assert "claim_id" not in model_sees["properties"]


def test_an_unexpected_error_fails_the_claim_not_the_run(
    backend, run, monkeypatch, memory_saver
):
    def broken(policy_id):
        raise RuntimeError("the backend fell over")

    monkeypatch.setattr(harness.api, "get_policy", broken)
    llm = stub(tool_call("get_policy", policy_id="POL-2001"))
    report = harness.work_claim("CLM-1001", run, FREE, memory_saver, llm)
    assert report == (
        "CLM-1001: failed, back in the queue (RuntimeError: the backend fell over)"
    )
    claim = backend.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "waiting"
    failure = backend.get("/api/claims/CLM-1001/steps").json()[-1]
    assert failure["kind"] == "failure"


def test_stopping_without_a_decision_is_a_failure(backend, run, memory_saver):
    first = harness.work_claim(
        "CLM-1001", run, FREE, memory_saver, stub(AIMessage(content="Hmm."))
    )
    assert first.startswith("CLM-1001: failed, back in the queue")
    second = harness.work_claim(
        "CLM-1001", run, FREE, memory_saver, stub(AIMessage(content="Hmm."))
    )
    assert second == f"CLM-1001: failed twice, left for a handler ({harness.STOPPED})"


def test_a_model_error_is_a_failure(backend, run, memory_saver):

    class Broken(StubModel):
        def _generate(self, *args, **kwargs):
            raise TimeoutError("the provider timed out")

    report = harness.work_claim(
        "CLM-1004", run, FREE, memory_saver, Broken(messages=iter([]))
    )
    assert "TimeoutError: the provider timed out" in report
    assert backend.get("/api/claims/CLM-1004").json()["status"] == "waiting"


def test_reports_say_where_each_claim_stands(backend, run, memory_saver):
    referred = harness.work_claim(
        "CLM-1010",
        run,
        FREE,
        memory_saver,
        stub(decide("refer", 0), AIMessage(content=".")),
    )
    assert referred == f"CLM-1010: referred to a handler, because: {REASONS}"
    declined = harness.work_claim(
        "CLM-1005",
        run,
        FREE,
        memory_saver,
        stub(decide("decline", 0), AIMessage(content=".")),
    )
    assert declined == f"CLM-1005: declined, because: {REASONS}"
    held = harness.work_claim(
        "CLM-1002",
        run,
        FREE,
        memory_saver,
        stub(decide("approve", 1150), AIMessage(content=".")),
    )
    assert held == "CLM-1002: approved $1,150.00, waiting for a handler's sign-off"


def test_usage_is_recorded_on_the_run(backend, run, memory_saver):
    priced = model("anthropic:claude-haiku-5-5")
    reply = AIMessage(
        content="",
        tool_calls=[{"name": "get_claim", "args": {}, "id": "1"}],
        usage_metadata={
            "input_tokens": 20000,
            "output_tokens": 1000,
            "total_tokens": 21000,
        },
    )
    harness.work_claim(
        "CLM-1001", run, priced, memory_saver, stub(reply, AIMessage(content="."))
    )
    usage = backend.get("/api/dispatches/latest").json()["usage"]
    assert usage["model_calls"] == 2
    assert usage["input_tokens"] == 20000
    assert usage["cost"] == pytest.approx(priced.cost(20000, 1000))


def test_instructions_list_the_sections_not_the_wording(backend):
    prompt = harness.instructions()
    assert prompt.startswith("# UnderCover claim agent")
    assert "- Claims manual 9. Repeat claims" in prompt
    assert "- Policy wording 3. Trip Delay" in prompt
    assert "# UnderCover Travel Insurance: Policy Wording" not in prompt


def test_sections_read_are_recorded(backend, run, memory_saver):
    harness.work_claim(
        "CLM-1001",
        run,
        FREE,
        memory_saver,
        stub(
            tool_call("search_documents", query="meals without receipts"),
            tool_call("read_section", document="manual", number=10),
            tool_call("read_section", document="manual", number=99),
            AIMessage(content="Read the manual."),
        ),
    )
    steps = backend.get("/api/claims/CLM-1001/steps").json()
    results = [s["text"] for s in steps if s["kind"] == "tool_result"]
    assert any('"title": "Meals without receipts"' in text for text in results)
    sections = [json.loads(s["text"]) for s in steps if s["kind"] == "section"]
    assert sections == [
        {
            "document": "manual",
            "document_title": "Claims manual",
            "number": 10,
            "title": "Meals without receipts",
        }
    ]
    refused = [s["text"] for s in steps if s["text"].startswith("Refused")]
    assert refused == ["Refused (404): There is no section 99 in the manual"]


@pytest.mark.parametrize(
    ("spec", "kind"),
    [
        ("openrouter:deepseek/deepseek-v4.1-flash", ChatOpenAI),
        ("anthropic:claude-haiku-5-5", ChatAnthropic),
        ("ollama:qwen3.5:4b", ChatOllama),
    ],
)
def test_chat_model_for_each_provider(spec, kind, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    allowed = model(spec)
    llm = harness.chat_model(allowed)
    assert isinstance(llm, kind)
    assert spec.endswith(getattr(llm, "model_name", None) or getattr(llm, "model", ""))
    for option, value in allowed.options.items():
        assert getattr(llm, option) == value


def test_chat_model_reaches_the_configured_address(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "http://openrouter.test/api")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test")
    monkeypatch.setenv("OLLAMA_NUM_CTX", "4096")
    openrouter = harness.chat_model(model("openrouter:deepseek/deepseek-v4.1-flash"))
    assert isinstance(openrouter, ChatOpenAI)
    assert openrouter.openai_api_base == "http://openrouter.test/api"
    ollama = harness.chat_model(model("ollama:qwen3.5:4b"))
    assert isinstance(ollama, ChatOllama)
    assert ollama.base_url == "http://ollama.test"
    assert ollama.num_ctx == 4096


def test_chat_model_times_out_and_leaves_retries_to_the_agents(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_TIMEOUT", "42")
    openrouter = harness.chat_model(model("openrouter:deepseek/deepseek-v4.1-flash"))
    assert isinstance(openrouter, ChatOpenAI)
    assert (openrouter.request_timeout, openrouter.max_retries) == (42.0, 0)
    anthropic = harness.chat_model(model("anthropic:claude-haiku-5-5"))
    assert isinstance(anthropic, ChatAnthropic)
    assert (anthropic.default_request_timeout, anthropic.max_retries) == (42.0, 0)
    ollama = harness.chat_model(model("ollama:qwen3.5:4b"))
    assert isinstance(ollama, ChatOllama)
    assert ollama.client_kwargs == {"timeout": 42.0}


def test_a_refusal_of_invalid_input_reads_as_text(backend):
    with pytest.raises(harness.api.Refused, match=r"Refused \(422\): \[") as refused:
        harness.api.pay_claim("CLM-1001", -5)
    assert refused.value.status == 422


def test_a_claim_is_untouched_when_its_agent_cannot_be_built(
    backend, run, monkeypatch, memory_saver
):
    def no_key(model):
        raise KeyError("ANTHROPIC_API_KEY")

    monkeypatch.setattr(harness, "chat_model", no_key)
    with pytest.raises(KeyError):
        harness.work_claim("CLM-1001", run, FREE, memory_saver)
    assert backend.get("/api/claims/CLM-1001").json()["status"] == "waiting"


def test_an_error_while_paying_leaves_the_approval_in_progress(
    backend, run, monkeypatch, memory_saver
):
    """A claim with a decision is never failed: the next run carries it on."""

    def broken(claim_id, amount):
        raise RuntimeError("the backend fell over")

    monkeypatch.setattr(harness.api, "pay_claim", broken)
    report = harness.work_claim(
        "CLM-1001", run, FREE, memory_saver, stub(decide("approve", 420.0))
    )
    assert report == (
        "CLM-1001: approved $420.00, not paid yet"
        " (then RuntimeError: the backend fell over)"
    )
    claim = backend.get("/api/claims/CLM-1001").json()
    assert (claim["status"], claim["payment"]) == ("in_progress", None)
    steps = backend.get("/api/claims/CLM-1001/steps").json()
    assert "failure" not in [s["kind"] for s in steps]


def costing(cost=None, tokens=(1200, 300)):
    """A reply that reads the claim, with its tokens, and the cost OpenRouter
    reports, if any."""
    reply = tool_call("get_claim")
    reply.usage_metadata = {
        "input_tokens": tokens[0],
        "output_tokens": tokens[1],
        "total_tokens": sum(tokens),
    }
    if cost is not None:
        reply.response_metadata = {"token_usage": {"cost": cost}}
    return reply


def test_the_cost_openrouter_reports_is_recorded(backend, memory_saver):
    llm = stub(costing(cost=0.0042), decide("approve", 420.0))
    harness.work_claim("CLM-1001", None, FREE, memory_saver, llm)
    first, second = model_calls("CLM-1001")
    assert (first["input_tokens"], first["output_tokens"]) == (1200, 300)
    assert first["cost"] == 0.0042
    assert second["cost"] == 0.0


def test_with_no_cost_reported_the_models_prices_are_used(backend, memory_saver):
    priced = model("anthropic:claude-haiku-5-5")
    llm = stub(costing(tokens=(20000, 1000)), decide("approve", 420.0))
    harness.work_claim("CLM-1001", None, priced, memory_saver, llm)
    first, _ = model_calls("CLM-1001")
    assert first["cost"] == pytest.approx(priced.cost(20000, 1000))
    assert first["model"] == "anthropic:claude-haiku-5-5"


def test_a_claim_worked_alone_records_its_calls_and_its_spell_with_no_run(
    backend, memory_saver
):
    llm = stub(tool_call("get_claim"), costing(), decide("approve", 420.0))
    harness.work_claim("CLM-1001", None, FREE, memory_saver, llm)
    thread_id = backend.get("/api/claims/CLM-1001").json()["thread_id"]
    calls = model_calls("CLM-1001")
    assert len(calls) == 3
    assert {(c["run_id"], c["thread_id"]) for c in calls} == {(None, thread_id)}
    [spell] = work_times("CLM-1001")
    assert (spell["run_id"], spell["thread_id"]) == (None, thread_id)
    assert 0 <= spell["seconds"] < 1


def test_both_attempts_of_a_claim_count_on_its_run(backend, run, memory_saver):
    harness.work_claim(
        "CLM-1001", run, FREE, memory_saver, stub(AIMessage(content="Hmm."))
    )
    harness.work_claim(
        "CLM-1001", run, FREE, memory_saver, stub(decide("approve", 420.0))
    )
    calls, spells = model_calls("CLM-1001"), work_times("CLM-1001")
    assert len({c["thread_id"] for c in calls}) == 2
    assert [c["run_id"] for c in calls] == [run, run]
    assert [s["run_id"] for s in spells] == [run, run]
    assert backend.get("/api/dispatches/latest").json()["usage"]["model_calls"] == 2


@pytest.fixture
def clock(monkeypatch):
    """The harness's clock, which a test can move on, as if time passed."""
    moved = {"by": 0.0}
    monkeypatch.setattr(harness, "monotonic", lambda: monotonic() + moved["by"])
    return moved


def held(backend, run, memory_saver):
    """CLM-1002 approved for $1,350.00 in a run, waiting for a sign-off."""
    harness.work_claim(
        "CLM-1002", run, FREE, memory_saver, stub(decide("approve", 1350.0))
    )
    assert backend.get("/api/claims/CLM-1002").json()["status"] == "awaiting_sign_off"


def review(backend, approved, note=""):
    body = {"handler_id": "HND-01", "approved": approved, "note": note}
    backend.post("/api/claims/CLM-1002/review", json=body)


def test_the_wait_for_a_sign_off_never_counts(backend, run, memory_saver, clock):
    held(backend, run, memory_saver)
    clock["by"] = 3600
    review(backend, approved=True)
    harness.carry_on("CLM-1002", None, FREE, memory_saver, StubModel(messages=iter([])))
    assert backend.get("/api/claims/CLM-1002").json()["status"] == "decided"
    before, after = work_times("CLM-1002")
    assert (before["run_id"], after["run_id"]) == (run, None)
    assert before["seconds"] + after["seconds"] < 1


def test_a_carry_on_after_a_rejection_makes_its_calls_with_no_run(
    backend, run, memory_saver, clock
):
    held(backend, run, memory_saver)
    clock["by"] = 3600
    review(backend, approved=False, note="The deductible is $100.00.")
    llm = stub(tool_call("get_claim"), decide("approve", 1250.0))
    harness.carry_on("CLM-1002", None, FREE, memory_saver, llm)
    calls = model_calls("CLM-1002")
    assert [c["run_id"] for c in calls] == [run, None, None]
    before, after = work_times("CLM-1002")
    assert (before["run_id"], after["run_id"]) == (run, None)
    assert before["seconds"] + after["seconds"] < 1


def test_a_spell_that_ends_in_an_error_is_still_recorded(backend, run, memory_saver):
    class BreaksAfterOne(StubModel):
        def _generate(self, *args, **kwargs):
            try:
                return super()._generate(*args, **kwargs)
            except (StopIteration, RuntimeError) as exhausted:
                raise TimeoutError("the provider timed out") from exhausted

    llm = BreaksAfterOne(messages=iter([tool_call("get_claim")]))
    report = harness.work_claim("CLM-1001", run, FREE, memory_saver, llm)
    assert report.startswith("CLM-1001: failed, back in the queue")
    assert len(model_calls("CLM-1001")) == 1
    [spell] = work_times("CLM-1001")
    assert spell["run_id"] == run
