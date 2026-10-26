"""Builds and runs the claim agents: the model, the claim graph for each claim,
and its work on the claim, reported in a line."""

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver

from agent import api, graph, tracing
from agent.config import Model
from agent.tools import ClaimContext
from settings import setting

# How a claim's report reads, by the claim's state and by the agent's decision
BY_STATE = {
    "decided": "paid",
    "in_progress": "not paid yet",
    "awaiting_sign_off": "waiting for a handler's sign-off",
    "waiting": "failed, back in the queue",
    "left_for_handler": "failed twice, left for a handler",
}
BY_DECISION = {"decline": "declined", "refer": "referred to a handler"}
STOPPED = "The agent stopped before finishing the claim: it replied with no decision"

# Our providers, and the LangChain integration that serves each one
INTEGRATIONS = {"openrouter": "openai", "anthropic": "anthropic", "ollama": "ollama"}


def timeout() -> float:
    return float(setting("MODEL_TIMEOUT"))


# How to reach each provider, from the settings. A call that takes too long
# fails, and only the agents retry it (the claim graph's model and the queue
# agent's middleware), not the provider's client.
CONNECTIONS: dict[str, Callable[[], dict[str, Any]]] = {
    "openrouter": lambda: {
        "base_url": setting("OPENROUTER_BASE_URL"),
        "api_key": setting("OPENROUTER_API_KEY"),
        "timeout": timeout(),
        "max_retries": 0,
    },
    "anthropic": lambda: {
        "api_key": setting("ANTHROPIC_API_KEY"),
        "timeout": timeout(),
        "max_retries": 0,
    },
    "ollama": lambda: {
        "base_url": setting("OLLAMA_BASE_URL"),
        "num_ctx": int(setting("OLLAMA_NUM_CTX")),
        "client_kwargs": {"timeout": timeout()},
    },
}


def chat_model(model: Model) -> BaseChatModel:
    """Build the chat model for one of the models allowed."""
    return init_chat_model(
        model.name,
        model_provider=INTEGRATIONS[model.provider],
        **CONNECTIONS[model.provider](),
        **model.options,
    )


def contents() -> str:
    """List the sections of the wording and the manual, for the agent to look up."""
    lines = [
        f"- {s['document_title']} {s['number']}. {s['title']}"
        for s in api.list_sections()
    ]
    return "## The sections you can read\n\n" + "\n".join(lines)


def instructions() -> str:
    """The claim agent's instructions and the documents' contents, from the API."""
    return f"{api.get_instructions('claim')}\n\n{contents()}"


def claim_graph(
    model: Model, saver: BaseCheckpointSaver[Any], llm: BaseChatModel | None = None
) -> graph.ClaimGraph:
    """The claim graph on a model, with the claim agent's instructions, saving its
    progress with `saver`."""
    return graph.claim_graph(llm or chat_model(model), model, saver, instructions())


def report(claim: dict[str, Any]) -> str:
    """The line a claim's work reports: its outcome, from the backend's record,
    with the reasons for a decline or a referral, which the handlers need."""
    claim_id, status = claim["claim_id"], claim["status"]
    decision = claim["decisions"][-1] if claim["decisions"] else None
    if decision is None or status == "left_for_handler":
        return f"{claim_id}: {BY_STATE[status]}"
    if decision["decision"] != "approve":
        outcome = BY_DECISION[decision["decision"]]
        return f"{claim_id}: {outcome}, because: {decision['reasons']}"
    return f"{claim_id}: approved ${decision['payout']:,.2f}, {BY_STATE[status]}"


def failed(context: ClaimContext, reason: str) -> str:
    """Record that work on a claim failed before it was decided, and report where
    the claim now stands. A failure after the decision changes nothing: the next
    run carries the claim on."""
    claim = api.get_claim(context.claim_id)
    if claim["status"] != "in_progress" or claim["decisions"]:
        return f"{report(claim)} (then {reason})"
    claim = api.fail_claim(context.claim_id, context.thread_id, reason)
    return f"{report(claim)} ({reason})"


def run_graph(
    claim_graph: graph.ClaimGraph,
    context: ClaimContext,
    start: dict[str, Any] | None,
    config: RunnableConfig,
) -> str:
    """Run the claim graph on the claim's thread, saving each step before the
    next, and report in a line: the decision and payout, or what went wrong,
    failing a claim left undecided."""
    claim = {"claim_id": context.claim_id, "thread_id": context.thread_id}
    try:
        claim_graph.invoke(
            start,
            context=context,
            config={
                **config,
                "run_name": "claim-agent",
                "metadata": {**config.get("metadata", {}), **claim},
                "configurable": {"thread_id": context.thread_id},
            },
            durability="sync",
        )
    except Exception as error:  # noqa: BLE001 - one bad claim never stops a run
        return failed(context, f"{type(error).__name__}: {error}")
    worked = api.get_claim(context.claim_id)
    if worked["status"] == "in_progress" and not worked["decisions"]:
        return failed(context, STOPPED)
    return report(worked)


def work_claim(
    claim_id: str,
    run_id: int,
    model: Model,
    saver: BaseCheckpointSaver[Any],
    llm: BaseChatModel | None = None,
) -> str:
    """Work one claim in a run as a new attempt on a new thread, in a trace of
    its own in the claim's session, and report in a line."""
    context = ClaimContext(
        run_id=run_id, claim_id=claim_id, thread_id=f"{claim_id}-{uuid4().hex[:8]}"
    )
    claim_graph_on_model = claim_graph(model, saver, llm)
    api.start_claim(claim_id, run_id, context.thread_id)
    start = {"messages": [HumanMessage(f"Claim {claim_id}")], "model_calls": 0}
    return tracing.claim_trace(
        "work-claim",
        claim_id,
        context.thread_id,
        lambda config: run_graph(claim_graph_on_model, context, start, config),
        run_id=str(run_id),
        model=model.spec,
    )
