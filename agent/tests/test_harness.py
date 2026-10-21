import json

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from agent import harness
from agent.config import model
from agent.tests.stub import StubModel


def tool_call(name, **args):
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": f"call-{name}"}]
    )


def stub(*replies):
    return StubModel(messages=iter(replies))


def decide(decision, payout):
    return tool_call(
        "decide_claim",
        decision=decision,
        payout=payout,
        reasons="The delay was covered and the costs were reasonable.",
        policy_section="Section 3, Trip Delay",
    )


def test_work_claim_approves_and_pays(backend):
    llm = stub(
        tool_call("get_claim"),
        tool_call("get_policy", policy_id="POL-2001"),
        tool_call("get_customer", customer_id="CUS-3001"),
        decide("approve", 420.0),
        tool_call("pay_claim", amount=420.0),
        AIMessage(content="Approved and paid $420.00."),
    )
    assert harness.work_claim("CLM-1001", llm) == "Approved and paid $420.00."
    claim = backend.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 420.0
    steps = backend.get("/api/claims/CLM-1001/steps").json()
    assert [s["kind"] for s in steps] == ["tool_call", "tool_result"] * 5 + ["reply"]
    assert steps[0]["text"] == "get_claim {}"
    assert '"story"' in steps[1]["text"]
    assert len({s["thread_id"] for s in steps}) == 1
    assert steps[0]["thread_id"].startswith("CLM-1001-")


def test_payment_over_the_limit_is_refused(backend):
    llm = stub(
        decide("approve", 1150.0),
        tool_call("pay_claim", amount=1150.0),
        AIMessage(content="Approved; the payment waits for sign-off."),
    )
    harness.work_claim("CLM-1002", llm)
    claim = backend.get("/api/claims/CLM-1002").json()
    assert claim["status"] == "awaiting_sign_off"
    assert claim["payment"] is None
    refusal = backend.get("/api/claims/CLM-1002/steps").json()[3]
    assert refusal["kind"] == "tool_result"
    assert refusal["text"] == (
        "Refused (409): A payout over $1,000.00 waits for a handler's sign-off"
    )


def test_a_tool_cannot_reach_another_claim(backend):
    """The claim comes from the run's context, so the model can't name another."""
    harness.work_claim(
        "CLM-1003",
        stub(decide("decline", 0), AIMessage(content="Declined.")),
    )
    assert backend.get("/api/claims/CLM-1003").json()["status"] == "decided"
    assert backend.get("/api/claims/CLM-1001").json()["status"] == "waiting"


def test_an_unexpected_error_stops_the_run(backend, monkeypatch):
    def broken(policy_id):
        raise RuntimeError("the backend fell over")

    monkeypatch.setattr(harness.api, "get_policy", broken)
    with pytest.raises(RuntimeError):
        harness.work_claim(
            "CLM-1001", stub(tool_call("get_policy", policy_id="POL-2001"))
        )


def test_instructions_list_the_sections_not_the_wording(backend):
    prompt = harness.instructions()
    assert prompt.startswith("# UnderCover Agent")
    assert "- Claims manual 9. Repeat claims" in prompt
    assert "- Policy wording 3. Trip Delay" in prompt
    assert "# UnderCover Travel Insurance: Policy Wording" not in prompt


def test_sections_read_are_recorded(backend):
    harness.work_claim(
        "CLM-1001",
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
    assert harness.steps(thinking) == [
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
    llm = harness.chat_model(model(spec))
    assert isinstance(llm, kind)
    assert spec.endswith(getattr(llm, "model_name", None) or getattr(llm, "model", ""))
