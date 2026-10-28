"""The claim graph on stub models, with its progress saved in memory."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langfuse.langchain import CallbackHandler

from agent import harness, versions
from agent.tests.stub import (
    FREE,
    REASONS,
    StubModel,
    call,
    calls,
    decide,
    stub,
    tool_call,
)
from backend.tests.direct_changes import set_approval_limit

DECISION = {
    "decision": "approve",
    "reasons": REASONS,
    "policy_section": "Section 3, Trip Delay",
}


def thread_of(backend, claim_id):
    return backend.get(f"/api/claims/{claim_id}").json()["thread_id"]


def thread(backend, claim_id) -> RunnableConfig:
    """The config that names the claim's thread, for its saved progress."""
    return {"configurable": {"thread_id": thread_of(backend, claim_id)}}


def saved(saver, backend, claim_id):
    """The claim graph's latest saved state for the claim's thread."""
    return harness.claim_graph(FREE, saver, stub()).get_state(thread(backend, claim_id))


def test_the_graph_has_the_nodes_and_edges_of_the_plan(backend, memory_saver):
    drawn = harness.claim_graph(FREE, memory_saver, stub()).get_graph()
    assert set(drawn.nodes) == {
        "__start__",
        "agent",
        "tools",
        "wait_for_sign_off",
        "pay",
        "__end__",
    }
    edges = {(edge.source, edge.target) for edge in drawn.edges}
    assert edges == {
        ("__start__", "agent"),
        ("agent", "tools"),
        ("agent", "__end__"),
        ("tools", "agent"),
        ("tools", "wait_for_sign_off"),
        ("tools", "pay"),
        ("tools", "__end__"),
        ("wait_for_sign_off", "pay"),
        ("wait_for_sign_off", "agent"),
        ("pay", "__end__"),
    }


def test_an_approval_over_the_limit_waits_for_a_sign_off(backend, run, memory_saver):
    report = harness.work_claim(
        "CLM-1003", run, FREE, memory_saver, stub(decide("approve", 3750.0))
    )
    assert report == "CLM-1003: approved $3,750.00, waiting for a handler's sign-off"
    claim = backend.get("/api/claims/CLM-1003").json()
    assert (claim["status"], claim["payment"]) == ("awaiting_sign_off", None)
    state = saved(memory_saver, backend, "CLM-1003")
    assert state.next == ("wait_for_sign_off",)
    assert len(state.interrupts) == 1


def test_the_graph_follows_the_backends_limit(backend, run, memory_saver):
    set_approval_limit(5000.0)
    report = harness.work_claim(
        "CLM-1003", run, FREE, memory_saver, stub(decide("approve", 3750.0))
    )
    assert report == "CLM-1003: approved $3,750.00, paid"


def test_a_decline_or_a_referral_is_never_paid(backend, run, memory_saver):
    for claim_id, decision in [("CLM-1005", "decline"), ("CLM-1010", "refer")]:
        harness.work_claim(claim_id, run, FREE, memory_saver, stub(decide(decision, 0)))
        assert backend.get(f"/api/claims/{claim_id}").json()["payment"] is None
        history = harness.claim_graph(FREE, memory_saver, stub()).get_state_history(
            thread(backend, claim_id)
        )
        assert all("pay" not in snapshot.next for snapshot in history)


def test_a_refused_decision_goes_back_to_the_agent(backend, run, memory_saver):
    llm = stub(decide("approve", 0), decide("approve", 420.0))
    report = harness.work_claim("CLM-1001", run, FREE, memory_saver, llm)
    assert report == "CLM-1001: approved $420.00, paid"
    steps = backend.get("/api/claims/CLM-1001/steps").json()
    assert steps[1]["text"].startswith("Refused (422)")


def test_the_agent_stops_at_its_limit_of_model_calls(backend, run, memory_saver):
    forever = StubModel(messages=(tool_call("get_claim") for _ in range(40)))
    report = harness.work_claim("CLM-1001", run, FREE, memory_saver, forever)
    assert report.startswith("CLM-1001: failed, back in the queue (TooManyModelCalls")
    assert backend.get("/api/dispatches/latest").json()["usage"]["model_calls"] == 30
    assert saved(memory_saver, backend, "CLM-1001").values["model_calls"] == 30


def test_a_provider_error_is_tried_again_twice(backend, run, memory_saver):
    class FailsTwice(StubModel):
        failures: int = 0

        def _generate(self, *args, **kwargs):
            if self.failures < versions.MODEL_RETRIES:
                self.failures += 1
                raise TimeoutError("the provider timed out")
            return super()._generate(*args, **kwargs)

    llm = FailsTwice(messages=iter([decide("decline", 0)]))
    assert harness.work_claim("CLM-1005", run, FREE, memory_saver, llm).startswith(
        "CLM-1005: declined"
    )


def test_a_failure_starts_afresh_on_a_new_thread(backend, run, memory_saver):
    seen = []

    class Recording(StubModel):
        def _generate(self, messages, *args, **kwargs):
            seen.append(messages)
            return super()._generate(messages, *args, **kwargs)

    harness.work_claim(
        "CLM-1001", run, FREE, memory_saver, stub(AIMessage(content="Unsure."))
    )
    first = thread_of(backend, "CLM-1001")
    harness.work_claim(
        "CLM-1001",
        run,
        FREE,
        memory_saver,
        Recording(messages=iter([decide("decline", 0)])),
    )
    claim = backend.get("/api/claims/CLM-1001").json()
    assert (claim["attempts"], claim["status"]) == (2, "decided")
    assert claim["thread_id"] != first
    [prompt] = seen
    assert [type(m) for m in prompt] == [SystemMessage, HumanMessage]
    assert prompt[1].content == "Claim CLM-1001"


def test_every_claim_graph_run_saves_each_step_and_is_traced(
    backend, run, memory_saver, monkeypatch
):
    invoked = []
    real = harness.run_graph

    def watched(claim_graph, context, start, config):
        invoked.append(config)
        return real(claim_graph, context, start, config)

    monkeypatch.setattr(harness, "run_graph", watched)
    durability = []
    invoke = type(harness.claim_graph(FREE, memory_saver, stub())).invoke

    def recorded(self, *args, **kwargs):
        durability.append(kwargs.get("durability"))
        return invoke(self, *args, **kwargs)

    monkeypatch.setattr(
        type(harness.claim_graph(FREE, memory_saver, stub())), "invoke", recorded
    )
    harness.work_claim("CLM-1005", run, FREE, memory_saver, stub(decide("decline", 0)))
    assert durability == ["sync"]
    [config] = invoked
    assert any(isinstance(handler, CallbackHandler) for handler in config["callbacks"])


def test_two_decisions_at_once_are_recorded_once(backend, run, memory_saver):
    """ToolNode runs a reply's tool calls side by side; the backend lets one
    decision through and treats the same one again as done."""
    twice = calls(
        call("decide_claim", **DECISION, payout=420.0),
        {**call("decide_claim", **DECISION, payout=420.0), "id": "second"},
    )
    report = harness.work_claim("CLM-1001", run, FREE, memory_saver, stub(twice))
    assert report == "CLM-1001: approved $420.00, paid"
    claim = backend.get("/api/claims/CLM-1001").json()
    assert len(claim["decisions"]) == 1
    assert claim["payment"]["amount"] == 420.0
