"""The dispatcher: a LangGraph graph with no model, in the style of
labs/week2day4.ipynb, that works a dispatch with up to N claim agents at once.
It lists the claims to work, sends each to a claim agent with a Send, and
finishes the run once every claim has come back. It saves no progress of its
own: each claim saves its own on its own thread, and the next dispatch finishes
what a stopped one left."""

import logging
import operator
import threading
from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import ExecutionInfo, Runtime
from langgraph.types import RetryPolicy, Send

from agent import api, harness
from agent.reports import IN_PROGRESS, WAITING

STATUS = "status"

log = logging.getLogger(__name__)

# A claim that hits a rate limit or a timeout waits about 10 seconds, then about
# 20, and carries on each time, on top of the model's own retries
RETRY = RetryPolicy(max_attempts=3, initial_interval=10, retry_on=harness.TRANSIENT)

# How a dispatch works one claim in a run: given the claim and the run, it
# reports in a line
Work = Callable[[str, int], str]


class ClaimToWork(TypedDict):
    """What each Send hands a claim agent: the claim."""

    claim_id: str


class Dispatch(TypedDict):
    """What the dispatcher keeps for one run: the claims to work, and the report
    line each one comes back with."""

    claims: list[str]
    reports: Annotated[list[str], operator.add]


@dataclass(frozen=True)
class DispatchContext:
    """What the dispatcher's nodes know: the run, how to work a claim in it, the
    claims the agent's service is carrying on after a review, which a dispatch
    leaves alone, and whether a handler has asked the run to stop."""

    run: dict[str, Any]
    work: Work
    resuming: Collection[str]
    stop: threading.Event


def queue_order(claim: dict[str, Any]) -> tuple[bool, str, str]:
    """Claims in progress first, then waiting ones, each oldest submitted first."""
    return claim[STATUS] != IN_PROGRESS, claim["submitted_on"], claim["claim_id"]


def list_claims(state: Dispatch, runtime: Runtime[DispatchContext]) -> dict[str, Any]:
    """The claims the dispatch works, recorded with it: those in progress, then
    the waiting ones, less any the agent's service is carrying on."""
    listed = sorted(
        (
            claim
            for claim in api.list_claims()
            if claim[STATUS] in (IN_PROGRESS, WAITING)
            and claim["claim_id"] not in runtime.context.resuming
        ),
        key=queue_order,
    )
    claim_ids = [claim["claim_id"] for claim in listed]
    api.record_run_claims(runtime.context.run["run_id"], claim_ids)
    return {"claims": claim_ids}


def fan_out(state: Dispatch) -> list[Send] | str:
    """Send each claim to a claim agent, or finish when there are none."""
    sends = [Send("work_claim", ClaimToWork(claim_id=c)) for c in state["claims"]]
    return sends or "finish_run"


def work_claim(state: ClaimToWork, runtime: Runtime[DispatchContext]) -> dict[str, Any]:
    """Work one claim, once more if its first attempt failed and put it back in
    the queue, unless a handler asked the run to stop or the service is carrying
    the claim on. A transient error before the last try goes to the
    RetryPolicy, which waits and carries the claim on; on the last try, and for
    any other error, the claim is left as it stands, for the next dispatch, so
    no claim stops the dispatch."""
    context, claim_id = runtime.context, state["claim_id"]
    if context.stop.is_set() or claim_id in context.resuming:
        return reported(f"{claim_id}: left for the next dispatch")
    try:
        report = context.work(claim_id, context.run["run_id"])
        if api.get_claim(claim_id)[STATUS] == WAITING and not context.stop.is_set():
            report = context.work(claim_id, context.run["run_id"])
    except harness.TRANSIENT as error:
        if attempt(runtime) < RETRY.max_attempts:
            raise
        report = left(claim_id, error)
    except Exception as error:  # noqa: BLE001 - one bad claim never stops a dispatch
        report = left(claim_id, error)
    return reported(report)


def reported(report: str) -> dict[str, Any]:
    """Print a claim's report as it comes, and add it to the dispatch's."""
    print(report, flush=True)
    return {"reports": [report]}


def attempt(runtime: Runtime[DispatchContext]) -> int:
    """Which try of a claim this is, from 1. LangGraph sets the execution info
    before every node runs."""
    return cast(ExecutionInfo, runtime.execution_info).node_attempt


def left(claim_id: str, error: Exception) -> str:
    """Report a claim whose work went wrong, as it stands, logging the error."""
    log.warning("%s was left for the next dispatch", claim_id, exc_info=error)
    return f"{claim_id}: left for the next dispatch ({type(error).__name__}: {error})"


def finish_run(state: Dispatch, runtime: Runtime[DispatchContext]) -> dict[str, Any]:
    """Finish the run once every claim is back, or mark it stopped when a handler
    asked it to stop; the backend builds its summary from its records."""
    context = runtime.context
    api.finish_run(context.run["run_id"], context.stop.is_set())
    return {}


def dispatcher() -> CompiledStateGraph[Dispatch, DispatchContext, Any, Any]:
    builder = StateGraph(Dispatch, context_schema=DispatchContext)
    builder.add_node("list_claims", list_claims)
    builder.add_node(
        "work_claim", work_claim, retry_policy=RETRY, input_schema=ClaimToWork
    )
    builder.add_node("finish_run", finish_run)
    builder.add_edge(START, "list_claims")
    builder.add_conditional_edges("list_claims", fan_out, ["work_claim", "finish_run"])
    builder.add_edge("work_claim", "finish_run")
    builder.add_edge("finish_run", END)
    return builder.compile()


def work_run(
    run: dict[str, Any],
    work: Work,
    resuming: Collection[str],
    stop: threading.Event,
) -> list[str]:
    """Work a dispatch with up to its N claim agents at once, and return each
    claim's report line."""
    context = DispatchContext(run=run, work=work, resuming=resuming, stop=stop)
    finished = dispatcher().invoke(
        {"claims": [], "reports": []},
        context=context,
        config={"max_concurrency": run["agents"]},
    )
    return finished["reports"]
