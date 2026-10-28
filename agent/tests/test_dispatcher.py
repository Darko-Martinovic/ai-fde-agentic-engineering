"""The dispatcher, working dispatches with claim agents side by side on stub
models, their progress saved in memory."""

import operator
import threading
from functools import partial
from typing import Annotated, TypedDict

import pytest
from langchain_core.exceptions import ModelRateLimitError, ModelTimeoutError
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from agent import api, connection, dispatcher, harness
from agent.dispatcher import RETRY as REAL_RETRY  # before the tests' own
from agent.tests.stub import FREE, ByClaim, decide, tool_call
from backend.tests.direct_changes import set_status
from backend.tests.sign_ins import DANA, headers

DECLINE = [decide("decline", 0)]


def waiting(backend):
    claims = backend.get("/api/claims").json()
    return [c["claim_id"] for c in claims if c["status"] == "waiting"]


def settle_all_but(backend, *kept):
    """Mark every waiting claim but those kept decided, behind the API's back,
    so a dispatch finds only the kept ones."""
    others = [claim_id for claim_id in waiting(backend) if claim_id not in kept]
    if others:
        set_status("decided", *others)


def scripted(scripts, model=ByClaim):
    """A stub model working each claim from its own replies."""
    return model(messages=iter([]), scripts={c: iter(r) for c, r in scripts.items()})


def dispatch(llm, memory_saver, agents=3, resuming=(), stop=None):
    """A new dispatch, worked with claim agents on `llm`; its report lines."""
    run = api.create_dispatch(agents)
    work = partial(
        harness.work_in_run, version=FREE, new_saver=lambda: memory_saver, llm=llm
    )
    return dispatcher.work_run(run, work, resuming, stop or threading.Event())


def latest(backend):
    return backend.get("/api/dispatches/latest").json()


def claim(backend, claim_id):
    return backend.get(f"/api/claims/{claim_id}").json()


def kinds(backend, claim_id):
    steps = backend.get(f"/api/claims/{claim_id}/steps").json()
    return [step["kind"] for step in steps]


def test_the_graph_is_the_labs_with_a_finish_after_the_workers():
    graph = dispatcher.dispatcher().get_graph()
    assert {(edge.source, edge.target) for edge in graph.edges} == {
        ("__start__", "list_claims"),
        ("list_claims", "work_claim"),
        ("list_claims", "finish_run"),
        ("work_claim", "finish_run"),
        ("finish_run", "__end__"),
    }


def test_the_workers_retry_rate_limits_and_timeouts_after_ten_seconds():
    assert REAL_RETRY.max_attempts == 3
    assert REAL_RETRY.initial_interval == 10
    assert REAL_RETRY.retry_on == (ModelRateLimitError, ModelTimeoutError)
    assert (dispatcher.RETRY.initial_interval, dispatcher.RETRY.jitter) == (0, False)
    policy = dispatcher.dispatcher().builder.nodes["work_claim"].retry_policy
    assert policy == dispatcher.RETRY


def test_never_more_than_n_claims_at_once(backend, memory_saver):
    """Each model call waits until three are in, or a moment has passed, so the
    count doesn't depend on timing."""
    active, peak = [0], [0]
    lock = threading.Condition()

    class Counting(ByClaim):
        def reply(self, claim_id):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
                lock.notify_all()
                lock.wait_for(lambda: active[0] >= 3, timeout=1)
            try:
                return super().reply(claim_id)
            finally:
                with lock:
                    active[0] -= 1

    claims = waiting(backend)[:6]
    settle_all_but(backend, *claims)
    dispatch(scripted({c: DECLINE for c in claims}, Counting), memory_saver)
    assert peak[0] == 3
    assert {claim(backend, c)["status"] for c in claims} == {"decided"}
    assert len({claim(backend, c)["thread_id"] for c in claims}) == 6


def test_it_works_progress_then_the_oldest_and_leaves_the_rest(backend, memory_saver):
    held = scripted({"CLM-1002": [decide("approve", 1150.0)]})
    harness.work_claim("CLM-1002", None, FREE, memory_saver, held)
    api.start_claim("CLM-1003", None, "CLM-1003-stopped")
    queue = {c["claim_id"]: c for c in backend.get("/api/claims").json()}
    still_waiting = sorted(
        (c for c in queue.values() if c["status"] == "waiting"),
        key=lambda c: (c["submitted_on"], c["claim_id"]),
    )
    llm = scripted({c: DECLINE for c in queue})
    dispatch(llm, memory_saver)
    worked = [c["claim_id"] for c in latest(backend)["claims"]]
    assert worked == ["CLM-1003"] + [c["claim_id"] for c in still_waiting]
    assert "CLM-1002" not in worked
    assert claim(backend, "CLM-1002")["status"] == "awaiting_sign_off"


def test_each_claim_saves_under_its_own_thread_and_a_pause_holds_only_it(
    backend, memory_saver
):
    settle_all_but(backend, "CLM-1001", "CLM-1003")
    llm = scripted(
        {
            "CLM-1001": [decide("approve", 420.0)],
            "CLM-1003": [decide("approve", 3750.0)],
        }
    )
    dispatch(llm, memory_saver)
    assert latest(backend)["status"] == "finished"
    held = claim(backend, "CLM-1003")
    assert held["status"] == "awaiting_sign_off"
    assert claim(backend, "CLM-1001")["status"] == "decided"
    saved = list(memory_saver.list(None))
    worked = {claim(backend, c)["thread_id"] for c in ("CLM-1001", "CLM-1003")}
    assert {item.config["configurable"]["thread_id"] for item in saved} >= worked
    assert {item.config["configurable"]["checkpoint_ns"] for item in saved} == {""}
    graph = harness.claim_graph(FREE, memory_saver, scripted({}))
    paused = graph.get_state({"configurable": {"thread_id": held["thread_id"]}})
    assert paused.next == ("wait_for_sign_off",)


class Flaky(ByClaim):
    """Fails each claim's model calls with an error, as a script asks with an
    exception in place of a reply."""

    def reply(self, claim_id):
        found = super().reply(claim_id)
        if isinstance(found, BaseException):
            raise found
        return found


# The claim graph's model tries a call three times before an error reaches the
# dispatcher, so a claim that hits one "once" there has three in its script
def hits(error, times):
    return [error] * (3 * times)


@pytest.mark.parametrize("error", [ModelRateLimitError, ModelTimeoutError])
def test_a_transient_error_carries_the_claim_on_as_the_same_attempt(
    backend, memory_saver, error
):
    settle_all_but(backend, "CLM-1004", "CLM-1005")
    script = [tool_call("get_claim"), *hits(error("slow down"), 1), *DECLINE]
    llm = scripted({"CLM-1004": script, "CLM-1005": DECLINE}, Flaky)
    dispatch(llm, memory_saver)
    worked = claim(backend, "CLM-1004")
    assert (worked["status"], worked["attempts"]) == ("decided", 1)
    assert len(worked["decisions"]) == 1
    assert "failure" not in kinds(backend, "CLM-1004")
    run = latest(backend)
    [spells] = [c for c in run["claims"] if c["claim_id"] == "CLM-1004"]
    assert spells["started_at"] is not None


@pytest.mark.parametrize("error", [ModelRateLimitError, ModelTimeoutError])
def test_a_claim_still_failing_after_its_retries_stays_in_progress(
    backend, memory_saver, error
):
    settle_all_but(backend, "CLM-1004", "CLM-1005")
    llm = scripted(
        {"CLM-1004": hits(error("slow down"), 3), "CLM-1005": DECLINE}, Flaky
    )
    reports = dispatch(llm, memory_saver)
    stuck = claim(backend, "CLM-1004")
    assert (stuck["status"], stuck["attempts"]) == ("in_progress", 1)
    assert "failure" not in kinds(backend, "CLM-1004")
    assert f"CLM-1004: left for the next dispatch ({error.__name__}: slow down)" in (
        reports
    )
    assert claim(backend, "CLM-1005")["status"] == "decided"
    run = latest(backend)
    assert run["status"] == "finished"
    assert run["summary"]["unfinished"] == ["CLM-1004"]


def test_a_claim_that_fails_is_tried_once_more_in_the_same_dispatch(
    backend, memory_saver
):
    settle_all_but(backend, "CLM-1004", "CLM-1005")
    broken = RuntimeError("the provider sent nonsense")
    llm = scripted(
        {
            "CLM-1004": [broken, broken, broken, *DECLINE],
            "CLM-1005": [broken] * 6 + DECLINE,
        },
        Flaky,
    )
    dispatch(llm, memory_saver)
    second = claim(backend, "CLM-1004")
    assert (second["status"], second["attempts"]) == ("decided", 2)
    twice = claim(backend, "CLM-1005")
    assert (twice["status"], twice["attempts"]) == ("left_for_handler", 2)
    assert latest(backend)["summary"]["left_for_handler"] == ["CLM-1005"]


def test_a_claim_another_process_started_is_reported_and_the_rest_worked(
    backend, memory_saver, monkeypatch
):
    settle_all_but(backend, "CLM-1004", "CLM-1005")
    start = api.start_claim

    def taken(claim_id, run_id, thread_id):
        if claim_id == "CLM-1004":
            raise connection.Refused(409, "Claim CLM-1004 has just been started")
        return start(claim_id, run_id, thread_id)

    monkeypatch.setattr(api, "start_claim", taken)
    reports = dispatch(scripted({"CLM-1005": DECLINE}), memory_saver)
    assert any(
        line.startswith("CLM-1004: left for the next dispatch (Refused")
        for line in reports
    )
    assert claim(backend, "CLM-1005")["status"] == "decided"


def test_the_next_dispatch_carries_on_what_a_stopped_one_left(backend, memory_saver):
    """A dispatch killed partway leaves its claims as a restart does: CLM-1001
    in progress after a step, and CLM-1003 signed off while the service was
    away."""
    settle_all_but(backend, "CLM-1001", "CLM-1003")
    killed = scripted(
        {"CLM-1001": [tool_call("get_claim"), KeyboardInterrupt()]}, Flaky
    )
    with pytest.raises(KeyboardInterrupt):
        harness.work_claim("CLM-1001", None, FREE, memory_saver, killed)
    held = scripted({"CLM-1003": [decide("approve", 3750.0)]})
    harness.work_claim("CLM-1003", None, FREE, memory_saver, held)
    body = {"approved": True, "note": ""}
    backend.post("/api/claims/CLM-1003/review", json=body, headers=headers(DANA))
    before = claim(backend, "CLM-1001")
    dispatch(scripted({"CLM-1001": DECLINE}), memory_saver)
    carried = claim(backend, "CLM-1001")
    assert (carried["thread_id"], carried["attempts"]) == (before["thread_id"], 1)
    assert carried["status"] == "decided"
    assert len(carried["decisions"]) == 1
    paid = claim(backend, "CLM-1003")
    assert (paid["status"], paid["payment"]["authorized_by"]) == ("decided", "HND-01")


def test_a_claim_the_service_is_carrying_on_is_left_alone(backend, memory_saver):
    settle_all_but(backend, "CLM-1003", "CLM-1005")
    api.start_claim("CLM-1003", None, "CLM-1003-resuming")
    dispatch(scripted({"CLM-1005": DECLINE}), memory_saver, resuming={"CLM-1003"})
    assert [c["claim_id"] for c in latest(backend)["claims"]] == ["CLM-1005"]


def test_stop_starts_no_more_claims_and_the_run_shows_stopped(backend, memory_saver):
    kept = waiting(backend)[:3]
    settle_all_but(backend, *kept)
    stop = threading.Event()

    class Stopping(ByClaim):
        def reply(self, claim_id):
            stop.set()
            return super().reply(claim_id)

    llm = scripted({c: DECLINE for c in kept}, Stopping)
    reports = dispatch(llm, memory_saver, agents=1, stop=stop)
    first, *rest = [c["claim_id"] for c in latest(backend)["claims"]]
    assert claim(backend, first)["status"] == "decided"
    for claim_id in rest:
        assert claim(backend, claim_id)["status"] == "waiting"
        assert f"{claim_id}: left for the next dispatch" in reports
    run = latest(backend)
    assert run["status"] == "stopped"
    assert run["summary"]["unfinished"] == rest


def test_a_dispatch_with_nothing_to_work_finishes(backend, memory_saver):
    settle_all_but(backend)
    assert dispatch(scripted({}), memory_saver) == []
    assert latest(backend)["status"] == "finished"


def test_the_dispatch_runs_with_its_n_as_max_concurrency(backend, monkeypatch):
    seen = []
    graph = type(dispatcher.dispatcher())
    invoke = graph.invoke

    def recorded(self, *args, **kwargs):
        seen.append(kwargs["config"]["max_concurrency"])
        return invoke(self, *args, **kwargs)

    monkeypatch.setattr(graph, "invoke", recorded)
    settle_all_but(backend)
    run = api.create_dispatch(7)
    dispatcher.work_run(run, lambda claim_id, run_id: "", (), threading.Event())
    assert seen == [7]


class Workers(TypedDict):
    claims: list[str]
    done: Annotated[list[str], operator.add]


def test_langgraphs_error_handler_still_reraises_when_workers_fail_side_by_side():
    """Why work_claim leaves a claim itself on its last try: in LangGraph 1.2.12
    a node's error_handler runs, and so does the node after the workers, but
    invoke raises the handled error anyway when two workers fail. Once a
    release stops that, the dispatcher can move to error_handler."""
    handled = []

    class Broken(Exception):
        pass

    def fail(state):
        raise Broken(state)

    def handle(state):
        handled.append("handled")
        return {"done": ["handled"]}

    builder = StateGraph(Workers)
    builder.add_node("list", lambda state: {"claims": ["a", "b"]})
    builder.add_node("work", fail, error_handler=handle)
    builder.add_node("finish", lambda state: {})
    builder.add_edge(START, "list")
    builder.add_conditional_edges(
        "list", lambda state: [Send("work", c) for c in state["claims"]], ["work"]
    )
    builder.add_edge("work", "finish")
    builder.add_edge("finish", END)
    with pytest.raises(Broken):
        builder.compile().invoke({"claims": [], "done": []})
    assert handled == ["handled", "handled"]


def test_a_reply_with_no_decision_fails_the_claim_as_before(backend, memory_saver):
    settle_all_but(backend, "CLM-1004")
    llm = scripted({"CLM-1004": [AIMessage(content="Hmm."), *DECLINE]})
    dispatch(llm, memory_saver)
    assert claim(backend, "CLM-1004")["attempts"] == 2


def test_a_claim_the_service_picks_up_after_the_listing_is_left_alone(
    backend, memory_saver
):
    settle_all_but(backend, "CLM-1004", "CLM-1005")
    resuming = set()

    class PickedUp(ByClaim):
        def reply(self, claim_id):
            resuming.add("CLM-1005")
            return super().reply(claim_id)

    llm = scripted({"CLM-1004": DECLINE, "CLM-1005": DECLINE}, PickedUp)
    reports = dispatch(llm, memory_saver, agents=1, resuming=resuming)
    assert claim(backend, "CLM-1005")["status"] == "waiting"
    assert "CLM-1005: left for the next dispatch" in reports


def test_a_claim_with_nothing_saved_to_carry_on_never_stops_a_dispatch(
    backend, memory_saver
):
    """CLM-1003's decision was made through the API, so the graph saved
    nothing: the dispatch reports it and works the rest."""
    settle_all_but(backend, "CLM-1003", "CLM-1005")
    api.start_claim("CLM-1003", None, "CLM-1003-api")
    api.decide_claim(
        "CLM-1003",
        {
            "decision": "approve",
            "payout": 3750.0,
            "reasons": "Set up through the API.",
            "policy_section": "Section 7, Emergency Medical",
        },
    )
    body = {"approved": True, "note": ""}
    backend.post("/api/claims/CLM-1003/review", json=body, headers=headers(DANA))
    reports = dispatch(scripted({"CLM-1005": DECLINE}), memory_saver)
    assert any(line.startswith("CLM-1003: not picked up") for line in reports)
    assert claim(backend, "CLM-1005")["status"] == "decided"
    assert latest(backend)["status"] == "finished"


def test_stop_lets_the_claims_already_working_finish(backend, memory_saver):
    kept = waiting(backend)[:4]
    settle_all_but(backend, *kept)
    stop = threading.Event()
    lock = threading.Condition()
    started = []

    class StopsMidway(ByClaim):
        def reply(self, claim_id):
            with lock:
                started.append(claim_id)
                lock.notify_all()
                lock.wait_for(lambda: len(started) >= 2, timeout=1)
            stop.set()
            return super().reply(claim_id)

    llm = scripted({c: DECLINE for c in kept}, StopsMidway)
    dispatch(llm, memory_saver, agents=2, stop=stop)
    statuses = [claim(backend, c)["status"] for c in kept]
    assert sorted(statuses) == ["decided", "decided", "waiting", "waiting"]
    assert latest(backend)["status"] == "stopped"
