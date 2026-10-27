from langchain_core.messages import AIMessage

import agent.__main__ as cli
from agent import harness, queue_agent, tracing
from agent.tests.stub import FREE, StubModel, decide, stub, tool_call

TYPE = "langfuse.observation.type"
INPUT = "langfuse.observation.input"
OUTPUT = "langfuse.observation.output"
SESSION = "session.id"
TAGS = "langfuse.trace.tags"
# The queue agent's middleware hooks, which are left out of its trace
HOOKS = {
    "ModelCallLimitMiddleware.before_model",
    "ModelCallLimitMiddleware.after_model",
}


def approves(monkeypatch):
    """Give every claim agent a stub model that reads the claim and approves
    $420.00, which the graph pays."""

    def model(chosen):
        return stub(tool_call("get_claim"), decide("approve", 420.0))

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
    thread_id = backend.get("/api/claims/CLM-1001/steps").json()[0]["thread_id"]
    for span in spans:
        assert span.context.trace_id == root.context.trace_id
        assert span.attributes[SESSION] == thread_id
        assert span.attributes["langfuse.trace.name"] == "work-claim"
    [agent] = named(spans, "claim-agent")
    assert agent.attributes[TYPE] == "agent"
    assert parent(spans, agent) == root
    metadata = "langfuse.observation.metadata.thread_id"
    assert agent.attributes[metadata] == f'"{thread_id}"'
    generations = [s for s in spans if s.attributes[TYPE] == "generation"]
    assert len(generations) == 2
    tools = [s.name for s in spans if s.attributes[TYPE] == "tool"]
    assert tools == ["get_claim", "decide_claim"]
    assert {"agent", "tools", "pay"} <= {span.name for span in spans}


def test_each_claim_has_a_session_of_its_own(backend, monkeypatch, traces):
    approves(monkeypatch)
    cli.work_claims(["CLM-1001", "CLM-1002"], FREE)
    claims = roots(traces())
    assert [root.attributes[INPUT] for root in claims] == ["CLM-1001", "CLM-1002"]
    for root in claims:
        claim = backend.get(f"/api/claims/{root.attributes[INPUT]}/steps").json()
        assert root.attributes[SESSION] == claim[0]["thread_id"]


def test_middleware_hooks_are_not_sent(backend, traces, memory_saver):
    queue_llm = stub(AIMessage(content="Nothing to do."), AIMessage(content="Done."))
    queue_agent.run_queue(1, FREE, memory_saver, queue_llm, stub())
    names = {span.name for span in traces()}
    assert names >= HOOKS
    assert {span.name for span in traces() if tracing.sent(span)} == names - HOOKS


def test_a_queue_runs_claims_are_traces_of_their_own(backend, traces, memory_saver):
    queue_llm = stub(
        tool_call("work_claim", claim_id="CLM-1001"),
        tool_call("work_claim", claim_id="CLM-1004"),
        AIMessage(content="Two claims worked."),
    )
    claim_llm = stub(
        decide("approve", 420.0),
        decide("decline", 0.0),
    )
    summary = queue_agent.run_queue(2, FREE, memory_saver, queue_llm, claim_llm)
    spans = traces()
    [run] = [root for root in roots(spans) if root.name == "run-queue"]
    assert run.attributes[INPUT] == "Work up to 2 waiting claims in this run."
    assert run.attributes[OUTPUT] == summary
    assert SESSION not in run.attributes
    [queue] = named(spans, "queue-agent")
    assert parent(spans, queue) == run
    handed_on = [span.attributes[OUTPUT] for span in named(spans, "work_claim")]
    assert any("CLM-1001: approved $420.00, paid" in out for out in handed_on)
    worked = [root for root in roots(spans) if root.name == "work-claim"]
    assert [root.attributes[INPUT] for root in worked] == ["CLM-1001", "CLM-1004"]
    for root in worked:
        assert root.context.trace_id != run.context.trace_id
        steps = backend.get(f"/api/claims/{root.attributes[INPUT]}/steps").json()
        assert root.attributes[SESSION] == steps[0]["thread_id"]
    assert worked[0].attributes[SESSION] != worked[1].attributes[SESSION]
    assert {parent(spans, claim) for claim in named(spans, "claim-agent")} == set(
        worked
    )


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
    assert len(replies) == 1
    assert all(reply.name is None for reply in replies)


def test_nothing_is_sent_with_tracing_off(backend, monkeypatch, traces):
    approves(monkeypatch)
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "false")
    cli.work_claims(["CLM-1001"], FREE)
    assert traces() == ()
    assert backend.get("/api/claims/CLM-1001").json()["status"] == "decided"


def test_a_claim_carried_on_is_traced_in_the_same_session(
    backend, run, memory_saver, traces
):
    harness.work_claim(
        "CLM-1003", run, FREE, memory_saver, stub(decide("approve", 3750.0))
    )
    body = {"handler_id": "HND-01", "approved": True, "note": ""}
    backend.post("/api/claims/CLM-1003/review", json=body)
    harness.carry_on("CLM-1003", run, FREE, memory_saver, stub())
    first, then = sorted(roots(traces()), key=lambda root: root.start_time or 0)
    assert (first.name, then.name) == ("work-claim", "carry-on")
    thread_id = backend.get("/api/claims/CLM-1003").json()["thread_id"]
    assert first.attributes[SESSION] == then.attributes[SESSION] == thread_id


def test_a_queue_runs_claims_carry_its_tag(backend, memory_saver, traces):
    queue_llm = stub(
        tool_call("work_claim", claim_id="CLM-1001"),
        tool_call("work_claim", claim_id="CLM-1004"),
        AIMessage(content="Two claims worked."),
    )
    claim_llm = stub(decide("approve", 420.0), decide("decline", 0.0))
    queue_agent.run_queue(2, FREE, memory_saver, queue_llm, claim_llm)
    run_id = backend.get("/api/runs/latest").json()["run_id"]
    spans = traces()
    agents = named(spans, "claim-agent")
    assert len(agents) == 2
    assert all(span.attributes[TAGS] == (f"run-{run_id}",) for span in agents)
    worked = [root for root in roots(spans) if root.name == "work-claim"]
    metadata = "langfuse.trace.metadata.run_id"
    assert all(root.attributes[metadata] == f'"{run_id}"' for root in worked)


def test_a_claim_worked_alone_has_no_tag(backend, memory_saver, traces):
    harness.work_claim(
        "CLM-1001", None, FREE, memory_saver, stub(decide("approve", 420.0))
    )
    assert all(TAGS not in span.attributes for span in traces())
