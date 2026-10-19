from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent import main
from agent.tests.stub import StubModel


def tool_call(name, **args):
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": f"call-{name}"}]
    )


def stub(*replies):
    return StubModel(messages=iter(replies))


def decide(claim_id, decision, payout):
    return tool_call(
        "decide_claim",
        claim_id=claim_id,
        decision=decision,
        payout=payout,
        reasons="The delay was covered and the costs were reasonable.",
        policy_section="Section 3, Trip Delay",
    )


def test_run_approves_and_pays(backend):
    llm = stub(
        tool_call("get_claim", claim_id="CLM-1001"),
        tool_call("get_policy", policy_id="POL-2001"),
        tool_call("get_customer", customer_id="CUS-3001"),
        decide("CLM-1001", "approve", 420.0),
        tool_call("pay_claim", claim_id="CLM-1001", amount=420.0),
        AIMessage(content="Approved and paid $420.00."),
    )
    assert main.run("CLM-1001", "thread-1", llm) == "Approved and paid $420.00."
    claim = backend.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 420.0
    steps = backend.get("/api/claims/CLM-1001/steps").json()
    assert [s["kind"] for s in steps] == ["tool_call", "tool_result"] * 5 + ["reply"]
    assert steps[0]["text"] == 'get_claim {"claim_id": "CLM-1001"}'
    assert '"story"' in steps[1]["text"]
    assert {s["thread_id"] for s in steps} == {"thread-1"}


def test_payment_over_the_limit_is_refused(backend):
    llm = stub(
        decide("CLM-1002", "approve", 1150.0),
        tool_call("pay_claim", claim_id="CLM-1002", amount=1150.0),
        AIMessage(content="Approved; the payment waits for sign-off."),
    )
    main.run("CLM-1002", "thread-2", llm)
    claim = backend.get("/api/claims/CLM-1002").json()
    assert claim["status"] == "awaiting_sign_off"
    assert claim["payment"] is None
    refusal = backend.get("/api/claims/CLM-1002/steps").json()[3]
    assert refusal["kind"] == "tool_result"
    assert refusal["text"] == (
        "Refused (409): A payout over $1,000.00 waits for a handler's sign-off"
    )


def test_system_prompt_holds_instructions_and_wording(backend):
    prompt = main.system_prompt(backend)
    assert prompt.startswith("# UnderCover Agent")
    assert "# UnderCover Travel Insurance: Policy Wording" in prompt


def test_steps_from_messages():
    assert main.steps(HumanMessage(content="Claim CLM-1001")) == []
    assert main.steps(ToolMessage(content="ok", tool_call_id="1")) == [
        ("tool_result", "ok")
    ]
    thinking = AIMessage(
        content="Reading the claim.",
        tool_calls=[{"name": "get_claim", "args": {"claim_id": "C"}, "id": "1"}],
    )
    assert main.steps(thinking) == [
        ("reply", "Reading the claim."),
        ("tool_call", 'get_claim {"claim_id": "C"}'),
    ]


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
