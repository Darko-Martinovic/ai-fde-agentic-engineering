import threading
from functools import partial

from langchain_core.messages import AIMessage

import agent.__main__ as cli
from agent import api, dispatcher, harness, improver, improver_api, rounds
from agent.tests.round_stubs import claim_agents, declines, says
from agent.tests.round_stubs import improver as improver_model
from agent.tests.stub import FREE, ByClaim, StubModel, decide, stub, tool_call
from backend.tests.direct_changes import set_status
from backend.tests.round_steps import CHANGE
from backend.tests.sign_ins import DANA, headers

# Every waiting claim but CLM-1001 and CLM-1004, so a dispatch works those two
DECIDED_ELSEWHERE = [
    *(f"CLM-{n}" for n in range(1002, 1026) if n != 1004),
    "CLM-1901",
]

TYPE = "langfuse.observation.type"
INPUT = "langfuse.observation.input"
OUTPUT = "langfuse.observation.output"
SESSION = "session.id"
TAGS = "langfuse.trace.tags"


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
    cli.main(["CLM-1001"])
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
    assert len(generations) == 3  # the security check's, then the claim agent's two
    tools = [s.name for s in spans if s.attributes[TYPE] == "tool"]
    assert tools == ["get_claim", "decide_claim"]
    assert {"agent", "tools", "pay"} <= {span.name for span in spans}


def test_each_claim_has_a_session_of_its_own(backend, monkeypatch, traces):
    approves(monkeypatch)
    cli.main(["CLM-1001"])
    cli.main(["CLM-1002"])
    claims = roots(traces())
    assert [root.attributes[INPUT] for root in claims] == ["CLM-1001", "CLM-1002"]
    for root in claims:
        claim = backend.get(f"/api/claims/{root.attributes[INPUT]}/steps").json()
        assert root.attributes[SESSION] == claim[0]["thread_id"]


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
    cli.main(["CLM-1001"])
    replies = [m for m in seen[-1] if isinstance(m, AIMessage)]
    assert len(replies) == 1
    assert all(reply.name is None for reply in replies)


def test_nothing_is_sent_with_tracing_off(backend, monkeypatch, traces):
    approves(monkeypatch)
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "false")
    cli.main(["CLM-1001"])
    assert traces() == ()
    assert backend.get("/api/claims/CLM-1001").json()["status"] == "decided"


def test_a_claim_carried_on_is_traced_in_the_same_session(
    backend, run, memory_saver, traces
):
    harness.work_claim(
        "CLM-1003", run, FREE, memory_saver, stub(decide("approve", 3750.0))
    )
    body = {"approved": True, "note": ""}
    backend.post("/api/claims/CLM-1003/review", json=body, headers=headers(DANA))
    harness.carry_on("CLM-1003", run, FREE, memory_saver, stub())
    first, then = sorted(roots(traces()), key=lambda root: root.start_time or 0)
    assert (first.name, then.name) == ("work-claim", "carry-on")
    thread_id = backend.get("/api/claims/CLM-1003").json()["thread_id"]
    assert first.attributes[SESSION] == then.attributes[SESSION] == thread_id


def test_a_claim_worked_alone_has_no_tag(backend, memory_saver, traces):
    harness.work_claim(
        "CLM-1001", None, FREE, memory_saver, stub(decide("approve", 420.0))
    )
    assert all(TAGS not in span.attributes for span in traces())


def test_a_dispatchs_claims_are_traces_of_their_own_tagged_with_it(
    backend, memory_saver, traces
):
    set_status("decided", *DECIDED_ELSEWHERE)
    run = api.create_dispatch(2)
    llm = ByClaim(
        messages=iter([]),
        scripts={
            "CLM-1001": iter([decide("approve", 420.0)]),
            "CLM-1004": iter([decide("decline", 0.0)]),
        },
    )
    work = partial(
        harness.work_in_run, version=FREE, new_saver=lambda: memory_saver, llm=llm
    )
    dispatcher.work_run(run, work, (), threading.Event())
    spans = traces()
    worked = roots(spans)
    assert sorted(root.attributes[INPUT] for root in worked) == ["CLM-1001", "CLM-1004"]
    assert len({root.context.trace_id for root in worked}) == 2
    for root in worked:
        steps = backend.get(f"/api/claims/{root.attributes[INPUT]}/steps").json()
        assert root.attributes[SESSION] == steps[0]["thread_id"]
        metadata = "langfuse.trace.metadata.run_id"
        assert root.attributes[metadata] == f'"{run["run_id"]}"'
    agents = named(spans, "claim-agent")
    assert len(agents) == 2
    assert all(a.attributes[TAGS] == (f"run-{run['run_id']}",) for a in agents)


def test_a_rounds_evaluation_claims_are_tagged_with_the_run_and_the_round(
    backend, memory_saver, traces
):
    round_id = improver_api.create_round("HND-01", "improver-t")["round_id"]
    run = improver_api.create_round_evaluation(round_id, "evaluation")
    work = partial(
        harness.work_in_run,
        version=FREE,
        new_saver=lambda: memory_saver,
        llm=claim_agents(declines),
    )
    dispatcher.work_run(run, work, (), threading.Event())
    agents = named(traces(), "claim-agent")
    assert len(agents) == 25
    tags = (f"run-{run['run_id']}", f"round-{round_id}")
    # Langfuse merges the trace's tags as a set, in no order of its own
    assert [sorted(agent.attributes[TAGS]) for agent in agents] == [sorted(tags)] * 25


def test_each_stretch_of_the_improver_is_a_trace_in_the_rounds_session(
    backend, memory_saver, traces
):
    round_id = improver_api.create_round("HND-01", "improver-t")["round_id"]
    model = improver_model(says("propose_change", **CHANGE), says())
    workers = rounds.RoundWorkers(
        model_for=lambda chosen: model,
        new_saver=lambda: memory_saver,
        evaluate=lambda run: None,
    )
    rounds.stretch(round_id, workers, None)
    review = {"handler_id": "HND-01", "approved": False, "note": "No."}
    improver_api.record_review(round_id, 1, review)
    rounds.stretch(round_id, workers, improver.resume(False, "No."))
    spans = traces()
    stretches = roots(spans)
    assert [root.name for root in stretches] == ["improver", "improver"]
    assert len({root.context.trace_id for root in stretches}) == 2
    assert all(span.attributes[SESSION] == "improver-t" for span in spans)
    agents = [s for s in named(spans, "improver") if s not in stretches]
    assert agents
    assert all(agent.attributes[TAGS] == (f"round-{round_id}",) for agent in agents)
