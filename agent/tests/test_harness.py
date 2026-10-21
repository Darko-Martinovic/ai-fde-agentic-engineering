import json

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from agent import harness, middleware
from agent.config import model
from agent.tests.stub import FREE, StubModel, decide, stub, tool_call
from agent.tools import CLAIM_TOOLS


def test_work_claim_approves_and_pays(backend, run):
    llm = stub(
        tool_call("get_claim"),
        tool_call("get_policy", policy_id="POL-2001"),
        tool_call("get_customer", customer_id="CUS-3001"),
        decide("approve", 420.0),
        tool_call("pay_claim", amount=420.0),
        AIMessage(content="Approved and paid $420.00."),
    )
    report = harness.work_claim("CLM-1001", run, FREE, llm)
    assert report == "CLM-1001: approved $420.00, paid"
    claim = backend.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 420.0
    steps = backend.get("/api/claims/CLM-1001/steps").json()
    assert [s["kind"] for s in steps] == ["tool_call", "tool_result"] * 5 + ["reply"]
    assert steps[0]["text"] == "get_claim {}"
    assert '"story"' in steps[1]["text"]
    assert len({s["thread_id"] for s in steps}) == 1
    assert steps[0]["thread_id"].startswith("CLM-1001-")


def test_payment_over_the_limit_is_refused(backend, run):
    llm = stub(
        decide("approve", 1150.0),
        tool_call("pay_claim", amount=1150.0),
        AIMessage(content="Approved; the payment waits for sign-off."),
    )
    harness.work_claim("CLM-1002", run, FREE, llm)
    claim = backend.get("/api/claims/CLM-1002").json()
    assert claim["status"] == "awaiting_sign_off"
    assert claim["payment"] is None
    refusal = backend.get("/api/claims/CLM-1002/steps").json()[3]
    assert refusal["kind"] == "tool_result"
    assert refusal["text"] == (
        "Refused (409): A payout over $1,000.00 waits for a handler's sign-off"
    )


def test_a_tool_cannot_reach_another_claim(backend, run):
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
        "CLM-1003", run, FREE, stub(elsewhere, AIMessage(content="Declined."))
    )
    assert backend.get("/api/claims/CLM-1003").json()["status"] == "decided"
    assert backend.get("/api/claims/CLM-1001").json()["status"] == "waiting"
    for claim_tool in CLAIM_TOOLS:
        model_sees = convert_to_openai_tool(claim_tool)["function"]["parameters"]
        assert "claim_id" not in model_sees["properties"]


def test_an_unexpected_error_fails_the_claim_not_the_run(backend, run, monkeypatch):
    def broken(policy_id):
        raise RuntimeError("the backend fell over")

    monkeypatch.setattr(harness.api, "get_policy", broken)
    llm = stub(tool_call("get_policy", policy_id="POL-2001"))
    report = harness.work_claim("CLM-1001", run, FREE, llm)
    assert report == (
        "CLM-1001: failed, back in the queue (RuntimeError: the backend fell over)"
    )
    claim = backend.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "waiting"
    failure = backend.get("/api/claims/CLM-1001/steps").json()[-1]
    assert failure["kind"] == "failure"


def test_stopping_without_a_decision_is_a_failure(backend, run):
    first = harness.work_claim("CLM-1001", run, FREE, stub(AIMessage(content="Hmm.")))
    assert first.startswith("CLM-1001: failed, back in the queue")
    second = harness.work_claim("CLM-1001", run, FREE, stub(AIMessage(content="Hmm.")))
    assert second == f"CLM-1001: failed twice, left for a handler ({harness.STOPPED})"


def test_a_model_error_is_a_failure(backend, run):

    class Broken(StubModel):
        def _generate(self, *args, **kwargs):
            raise TimeoutError("the provider timed out")

    report = harness.work_claim("CLM-1004", run, FREE, Broken(messages=iter([])))
    assert "TimeoutError: the provider timed out" in report
    assert backend.get("/api/claims/CLM-1004").json()["status"] == "waiting"


def test_reports_say_where_each_claim_stands(backend, run):
    referred = harness.work_claim(
        "CLM-1010", run, FREE, stub(decide("refer", 0), AIMessage(content="."))
    )
    assert referred == "CLM-1010: referred to a handler"
    declined = harness.work_claim(
        "CLM-1005", run, FREE, stub(decide("decline", 0), AIMessage(content="."))
    )
    assert declined == "CLM-1005: declined"
    held = harness.work_claim(
        "CLM-1002", run, FREE, stub(decide("approve", 1150), AIMessage(content="."))
    )
    assert held == "CLM-1002: approved $1,150.00, waiting for a handler's sign-off"


def test_usage_is_recorded_on_the_run(backend, run):
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
    harness.work_claim("CLM-1001", run, priced, stub(reply, AIMessage(content=".")))
    usage = backend.get("/api/runs/latest").json()["usage"]
    assert usage["model_calls"] == 2
    assert usage["input_tokens"] == 20000
    assert usage["cost"] == pytest.approx(priced.cost(20000, 1000))


def test_instructions_list_the_sections_not_the_wording(backend):
    prompt = harness.instructions()
    assert prompt.startswith("# UnderCover claim agent")
    assert "- Claims manual 9. Repeat claims" in prompt
    assert "- Policy wording 3. Trip Delay" in prompt
    assert "# UnderCover Travel Insurance: Policy Wording" not in prompt


def test_sections_read_are_recorded(backend, run):
    harness.work_claim(
        "CLM-1001",
        run,
        FREE,
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


def test_steps_from_a_reply():
    thinking = AIMessage(
        content="Reading the claim.",
        tool_calls=[{"name": "get_policy", "args": {"policy_id": "P"}, "id": "1"}],
    )
    assert middleware.steps(thinking) == [
        ("reply", "Reading the claim."),
        ("tool_call", 'get_policy {"policy_id": "P"}'),
    ]


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


def test_a_refusal_of_invalid_input_reads_as_text(backend):
    with pytest.raises(harness.api.Refused, match=r"Refused \(422\): \[") as refused:
        harness.api.pay_claim("CLM-1001", -5)
    assert refused.value.status == 422


def test_an_error_after_the_decision_leaves_the_decision(backend, run):
    class FailsLast(StubModel):
        def _generate(self, messages, *args, **kwargs):
            if len(messages) > 2:
                raise TimeoutError("the provider timed out")
            return super()._generate(messages, *args, **kwargs)

    llm = FailsLast(messages=iter([decide("decline", 0)]))
    report = harness.work_claim("CLM-1005", run, FREE, llm)
    assert report == "CLM-1005: declined (then TimeoutError: the provider timed out)"
    assert backend.get("/api/claims/CLM-1005").json()["status"] == "decided"


def test_a_claim_is_untouched_when_its_agent_cannot_be_built(backend, run, monkeypatch):
    def no_key(model):
        raise KeyError("ANTHROPIC_API_KEY")

    monkeypatch.setattr(harness, "chat_model", no_key)
    with pytest.raises(KeyError):
        harness.work_claim("CLM-1001", run, FREE)
    assert backend.get("/api/claims/CLM-1001").json()["status"] == "waiting"
