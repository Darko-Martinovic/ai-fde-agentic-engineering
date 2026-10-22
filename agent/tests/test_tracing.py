from langchain_core.messages import AIMessage

import agent.__main__ as cli
from agent import harness, tracing
from agent.tests.stub import FREE, StubModel, decide, stub, tool_call

TYPE = "langfuse.observation.type"
INPUT = "langfuse.observation.input"
OUTPUT = "langfuse.observation.output"
SESSION = "session.id"
HOOKS = {
    "ModelCallLimitMiddleware.before_model",
    "ModelCallLimitMiddleware.after_model",
    "StepRecorder.after_model",
}


def approves(monkeypatch):
    """Give every claim agent a stub model that approves $420.00 and pays it."""

    def model(chosen):
        return stub(
            tool_call("get_claim"),
            decide("approve", 420.0),
            tool_call("pay_claim", amount=420.0),
            AIMessage(content="Approved and paid $420.00."),
        )

    monkeypatch.setattr(harness, "chat_model", model)


def named(spans, name):
    return [span for span in spans if span.name == name]


def roots(spans):
    """The spans with no parent among those sent: one for each trace."""
    ids = {span.context.span_id for span in spans}
    return [s for s in spans if s.parent is None or s.parent.span_id not in ids]


def parent(spans, span):
    [found] = [s for s in spans if s.context.span_id == span.parent.span_id]
    return found


def test_a_claim_named_is_a_trace_of_its_own(backend, monkeypatch, traces):
    approves(monkeypatch)
    cli.work_claims(["CLM-1001"], FREE)
    spans = traces()
    [root] = roots(spans)
    assert (root.name, root.attributes[INPUT]) == ("work-claim", "CLM-1001")
    assert root.attributes[OUTPUT] == "CLM-1001: approved $420.00, paid"
    for span in spans:
        assert span.context.trace_id == root.context.trace_id
        assert span.attributes[SESSION].startswith("run-1-")
        assert span.attributes["langfuse.trace.name"] == "work-claim"
    [agent] = named(spans, "claim-agent")
    assert agent.attributes[TYPE] == "agent"
    assert parent(spans, agent) == root
    thread_id = backend.get("/api/claims/CLM-1001/steps").json()[0]["thread_id"]
    metadata = "langfuse.observation.metadata.thread_id"
    assert agent.attributes[metadata] == f'"{thread_id}"'
    generations = [s for s in spans if s.attributes[TYPE] == "generation"]
    assert len(generations) == 4
    tools = [s.name for s in spans if s.attributes[TYPE] == "tool"]
    assert tools == ["get_claim", "decide_claim", "pay_claim"]


def test_the_claims_of_one_run_share_its_session(backend, monkeypatch, traces):
    approves(monkeypatch)
    cli.work_claims(["CLM-1001", "CLM-1002"], FREE)
    cli.work_claims(["CLM-1004"], FREE)
    claims = roots(traces())
    assert [root.attributes[INPUT] for root in claims] == [
        "CLM-1001",
        "CLM-1002",
        "CLM-1004",
    ]
    sessions = [root.attributes[SESSION] for root in claims]
    assert sessions[0] == sessions[1] != sessions[2]


def test_middleware_hooks_are_not_sent(backend, monkeypatch, traces):
    approves(monkeypatch)
    cli.work_claims(["CLM-1001"], FREE)
    names = {span.name for span in traces()}
    assert names >= HOOKS
    assert {span.name for span in traces() if tracing.sent(span)} == names - HOOKS


def test_a_queue_run_is_one_trace_with_its_claim_agents_inside(backend, traces):
    queue_llm = stub(
        tool_call("work_claim", claim_id="CLM-1001"),
        AIMessage(content="One claim worked."),
    )
    claim_llm = stub(
        decide("approve", 420.0),
        tool_call("pay_claim", amount=420.0),
        AIMessage(content="Approved and paid $420.00."),
    )
    summary = harness.run_queue(1, FREE, queue_llm, claim_llm)
    spans = traces()
    [root] = roots(spans)
    assert root.name == "run-queue"
    assert root.attributes[INPUT] == "Work up to 1 waiting claims in this run."
    assert root.attributes[OUTPUT] == summary
    [queue] = named(spans, "queue-agent")
    assert parent(spans, queue) == root
    [handed_on] = named(spans, "work_claim")
    [claim] = named(spans, "claim-agent")
    assert claim.attributes[TYPE] == "agent"
    assert parent(spans, claim) == handed_on
    assert "CLM-1001: approved $420.00, paid" in handed_on.attributes[OUTPUT]


def test_naming_the_agents_leaves_the_conversation_alone(backend, monkeypatch):
    """The agents are named in the trace only: the model sees no name on its
    own replies."""
    seen = []
    generate = StubModel._generate

    def recording(self, messages, *args, **kwargs):
        seen.append(messages)
        return generate(self, messages, *args, **kwargs)

    monkeypatch.setattr(StubModel, "_generate", recording)
    approves(monkeypatch)
    cli.work_claims(["CLM-1001"], FREE)
    replies = [m for m in seen[-1] if isinstance(m, AIMessage)]
    assert len(replies) == 3
    assert all(reply.name is None for reply in replies)


def test_nothing_is_sent_with_tracing_off(backend, monkeypatch, traces):
    approves(monkeypatch)
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "false")
    cli.work_claims(["CLM-1001"], FREE)
    assert traces() == ()
    assert backend.get("/api/claims/CLM-1001").json()["status"] == "decided"
