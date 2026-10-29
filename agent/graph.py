"""The claim agent as a LangGraph graph of our own, as in labs/week2day3.ipynb:
its state, its nodes and its edges. A security check reads the claim first and
refers one that tries to instruct whoever handles it; otherwise the agent works
the claim with its tools, and the graph pays an approval the backend can pay at
once, or waits with interrupt() for a handler's review of one held for
sign-off: the sign-off pays it in the backend, and a rejection comes back to
the agent. Its nodes record each step and each
model call on the claim."""

import time
from collections.abc import Callable
from functools import partial
from typing import Annotated, Any, NotRequired, TypedDict, cast

from langchain.tools import ToolException
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import ToolCallRequest, ToolInvocationError
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from agent import api, recording, screening
from agent.connection import Refused
from agent.reports import IN_PROGRESS
from agent.tools import CLAIM_TOOLS, ClaimContext, read_section
from agent.versions import Model

# A claim agent's model calls before it's stopped, across restarts
MAX_MODEL_CALLS = 30
# The retries of a model call that fails at the provider, the first after this
# many seconds
MODEL_RETRIES = 2
RETRY_DELAY = 1.0


def latest(_: Any, new: Any) -> Any:
    """Keep the latest value, as when the agent records two decisions at once."""
    return new


class ClaimState(TypedDict):
    """What the claim graph keeps for one claim, saved after every step: the
    conversation, the model calls made, which stay limited across a restart,
    and the decision and the claim's status as the backend recorded them."""

    messages: Annotated[list[AnyMessage], add_messages]
    model_calls: int
    decision: NotRequired[Annotated[str | None, latest]]
    status: NotRequired[Annotated[str | None, latest]]


ClaimGraph = CompiledStateGraph[ClaimState, ClaimContext, Any, Any]
Reply = Runnable[LanguageModelInput, BaseMessage]


class TooManyModelCalls(Exception):
    """The claim agent reached its limit of model calls without deciding."""


def screen(
    state: ClaimState,
    runtime: Runtime[ClaimContext],
    *,
    check: screening.Check,
    model: Model,
) -> dict[str, Any]:
    """Run the security check on the claim before the agent's model sees it,
    recording each of the check's model calls and its result. A claim that tries
    to instruct whoever handles it is referred with the check's reason, and the
    agent's model never sees it. As the graph's first node, it runs once for each
    thread: a carry-on from saved progress starts after it."""
    context = runtime.context
    claim = api.get_claim(context.claim_id)
    found = screening.screen_claim(
        check, claim, partial(recording.model_call, context, model)
    )
    recording.check(context, found.instructions_found, found.reason)
    if not found.instructions_found:
        return {}
    referred = api.record_decision(
        context.claim_id,
        {
            "decision": "refer",
            "payout": 0,
            "reasons": found.reason,
            "policy_section": screening.SECURITY_CHECK,
        },
    )
    return {"decision": "refer", "status": referred["status"]}


def agent(
    state: ClaimState,
    runtime: Runtime[ClaimContext],
    *,
    llm: Reply,
    model: Model,
    instructions: SystemMessage,
) -> dict[str, Any]:
    """Call the model with the conversation so far, recording its reply as steps
    on the claim and the call's tokens, cost and time on the claim."""
    if state["model_calls"] >= MAX_MODEL_CALLS:
        raise TooManyModelCalls(f"the agent made {MAX_MODEL_CALLS} model calls")
    started = time.monotonic()
    reply = cast(AIMessage, llm.invoke([instructions, *state["messages"]]))
    recording.model_call(runtime.context, model, reply, time.monotonic() - started)
    recording.reply(runtime.context, reply)
    return {"messages": [reply], "model_calls": state["model_calls"] + 1}


def refusal(error: Exception) -> str:
    """Give the backend's refusal, or a tool called the wrong way, back to the
    model as text. Any other error stops the graph, and the harness fails the
    claim."""
    if isinstance(error, ToolInvocationError):
        return error.message
    if isinstance(error, Refused | ToolException):
        return str(error)
    raise error


def record_result(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
) -> ToolMessage | Command[Any]:
    """Run one tool call and record its result on the claim, with any section it
    read."""
    result = execute(request)
    message = (
        result
        if isinstance(result, ToolMessage)
        else cast(dict[str, Any], result.update)["messages"][-1]
    )
    context = cast(ClaimContext, request.runtime.context)
    recording.tool_result(context, message)
    if request.tool_call["name"] == read_section.name and message.status != "error":
        recording.section(context, str(message.text))
    return result


def wait_for_sign_off(state: ClaimState) -> Command[Any]:
    """Wait for a handler's review of the held payout, which the graph is resumed
    with: a sign-off ends the work, as the backend paid the claim when it was
    signed off, and a rejection takes the handler's note back to the agent,
    which decides again. Nothing comes before the interrupt, as a resumed node
    runs again from the top."""
    review = interrupt(
        {"decision": state.get("decision"), "status": state.get("status")}
    )
    if review["approved"]:
        return Command(goto=END)
    note = HumanMessage(f"A handler rejected the payout: {review['note']}")
    # The agent works the claim again with a fresh allowance of model calls
    return Command(
        goto="agent",
        update={
            "messages": [note],
            "decision": None,
            "status": None,
            "model_calls": 0,
        },
    )


def pay(state: ClaimState, runtime: Runtime[ClaimContext]) -> dict[str, Any]:
    """Pay the claim its approved payout. Paying again after a restart is
    harmless: the backend treats a repeat as done."""
    claim_id = runtime.context.claim_id
    payout = api.get_claim(claim_id)["decisions"][-1]["payout"]
    return {"status": api.pay_claim(claim_id, payout)["status"]}


def after_screen(state: ClaimState) -> str:
    """End on the check's referral, or let the agent work the claim."""
    return END if state.get("decision") else "agent"


def after_agent(state: ClaimState) -> str:
    """Run the tools the model asked for. A reply with none ends the work, and
    the harness fails a claim left undecided."""
    last = state["messages"][-1]
    return "tools" if isinstance(last, AIMessage) and last.tool_calls else END


def after_tools(state: ClaimState) -> str:
    """Follow the backend's reply to the decision: wait for a sign-off, pay an
    approval it can pay now, or end on a decline or a referral."""
    status, decision = state.get("status"), state.get("decision")
    if decision is None:
        return "agent"
    if status == "awaiting_sign_off":
        return "wait_for_sign_off"
    if decision == "approve" and status == IN_PROGRESS:
        return "pay"
    return END


def retried[In, Out](model: Runnable[In, Out]) -> Runnable[In, Out]:
    """A model call retried when it fails at the provider."""
    return model.with_retry(
        stop_after_attempt=MODEL_RETRIES + 1,
        exponential_jitter_params={"initial": RETRY_DELAY, "jitter": 0},
    )


def claim_graph(
    llm: BaseChatModel,
    model: Model,
    saver: BaseCheckpointSaver[Any],
    prompt: str,
    check: tuple[screening.Check, Model],
) -> ClaimGraph:
    """Build the claim graph on a model, with the security check's model and
    what it runs on, saving its progress with `saver`."""
    builder = StateGraph(ClaimState, context_schema=ClaimContext)
    replies = retried(llm.bind_tools(CLAIM_TOOLS))
    check_model, check_runs_on = check
    builder.add_node(
        "screen", partial(screen, check=retried(check_model), model=check_runs_on)
    )
    builder.add_node(
        "agent",
        partial(agent, llm=replies, model=model, instructions=SystemMessage(prompt)),
    )
    builder.add_node(
        "tools",
        ToolNode(CLAIM_TOOLS, handle_tool_errors=refusal, wrap_tool_call=record_result),
    )
    builder.add_node(
        "wait_for_sign_off", wait_for_sign_off, destinations=(END, "agent")
    )
    builder.add_node("pay", pay)
    builder.add_edge(START, "screen")
    builder.add_conditional_edges("screen", after_screen, ["agent", END])
    builder.add_conditional_edges("agent", after_agent, ["tools", END])
    builder.add_conditional_edges(
        "tools", after_tools, ["agent", "wait_for_sign_off", "pay", END]
    )
    builder.add_edge("pay", END)
    return builder.compile(checkpointer=saver)
