"""Builds and runs the UnderCover Agent: its model, the middleware around it,
and its runs."""

import threading
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    ToolErrorMiddleware,
)
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from agent import api, tracing
from agent.config import Model
from agent.middleware import StepRecorder, UsageRecorder, refusal
from agent.tools import (
    CLAIM_TOOLS,
    QUEUE_TOOLS,
    ClaimContext,
    RunContext,
    waiting_claims,
)
from settings import setting

# A claim agent's model calls before it's stopped, and the retries of a call
# that fails at the provider, the first after this many seconds
MAX_MODEL_CALLS = 30
MODEL_RETRIES = 2
RETRY_DELAY = 1.0

# How a claim's report reads, by the claim's state and by the agent's decision
BY_STATE = {
    "decided": "paid",
    "awaiting_sign_off": "waiting for a handler's sign-off",
    "waiting": "failed, back in the queue",
    "left_for_handler": "failed twice, left for a handler",
}
BY_DECISION = {"decline": "declined", "refer": "referred to a handler"}
# The queue agent's model calls: a few for each claim, and some to plan and sum up
QUEUE_CALLS_A_CLAIM = 4
QUEUE_CALLS = 10
MISSED = (
    "Before you finish: these claims are still waiting, and this run should work"
    " them: {claims}. Work them, update your to-do list, then give your summary."
)
LEFT_WAITING = "Still waiting, though this run should have worked them: {claims}."
STOPPED = (
    "The agent stopped before finishing the claim: it replied with no decision"
    " or an approval left unpaid, or reached its limit of"
    f" {MAX_MODEL_CALLS} model calls"
)

# Our providers, and the LangChain integration that serves each one
INTEGRATIONS = {"openrouter": "openai", "anthropic": "anthropic", "ollama": "ollama"}


def timeout() -> float:
    return float(setting("MODEL_TIMEOUT"))


# How to reach each provider, from the settings. A call that takes too long
# fails, and only ModelRetryMiddleware retries it, not the provider's client.
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


def middleware(
    model: Model, model_calls: int, *more: AgentMiddleware[Any, Any]
) -> list[AgentMiddleware[Any, Any]]:
    """What every agent has around its calls: usage recorded, provider errors
    retried, its model calls capped and refusals given back as text."""
    return [
        UsageRecorder(model),
        ModelRetryMiddleware(
            max_retries=MODEL_RETRIES, on_failure="error", initial_delay=RETRY_DELAY
        ),
        ModelCallLimitMiddleware(run_limit=model_calls, exit_behavior="end"),
        *more,
        ToolErrorMiddleware(refusal),
    ]


def claim_agent(
    llm: BaseChatModel, model: Model
) -> CompiledStateGraph[Any, Any, Any, Any]:
    return create_agent(
        llm,
        tools=CLAIM_TOOLS,
        system_prompt=instructions(),
        context_schema=ClaimContext,
        middleware=middleware(model, MAX_MODEL_CALLS, StepRecorder()),
    )


def queue_agent(
    llm: BaseChatModel, model: Model, cap: int
) -> CompiledStateGraph[Any, Any, Any, Any]:
    return create_agent(
        llm,
        tools=QUEUE_TOOLS,
        system_prompt=api.get_instructions("queue"),
        context_schema=RunContext,
        middleware=middleware(model, QUEUE_CALLS_A_CLAIM * cap + QUEUE_CALLS),
    )


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
    the claim now stands. A failure after the decision changes nothing."""
    claim = api.get_claim(context.claim_id)
    if claim["status"] != "in_progress":
        return f"{report(claim)} (then {reason})"
    claim = api.fail_claim(context.claim_id, context.thread_id, reason)
    return f"{report(claim)} ({reason})"


def run_claim_agent(
    agent: CompiledStateGraph[Any, Any, Any, Any],
    context: ClaimContext,
    config: RunnableConfig,
) -> str:
    """Run the claim agent on its claim and report in a line: the decision and
    payout, or what went wrong, failing a claim it left undecided."""
    claim = {"claim_id": context.claim_id, "thread_id": context.thread_id}
    metadata = {**config.get("metadata", {}), **claim}
    try:
        agent.invoke(
            {"messages": [{"role": "user", "content": f"Claim {context.claim_id}"}]},
            context=context,
            config={**config, "run_name": "claim-agent", "metadata": metadata},
        )
    except Exception as error:  # noqa: BLE001 - one bad claim never stops a run
        return failed(context, f"{type(error).__name__}: {error}")
    if api.get_claim(context.claim_id)["status"] == "in_progress":
        return failed(context, STOPPED)
    return report(api.get_claim(context.claim_id))


def work_claim(
    claim_id: str, run_id: int, model: Model, llm: BaseChatModel | None = None
) -> str:
    """Work one claim in a run from a clean start, in a trace of its own in the
    claim's session, and report in a line."""
    context = ClaimContext(
        run_id=run_id, claim_id=claim_id, thread_id=f"{claim_id}-{uuid4().hex[:8]}"
    )
    agent = claim_agent(llm or chat_model(model), model)
    api.start_claim(claim_id, run_id, context.thread_id)
    return tracing.claim_trace(
        "work-claim",
        claim_id,
        context.thread_id,
        lambda config: run_claim_agent(agent, context, config),
        run_id=str(run_id),
        model=model.spec,
    )


def missed(started: list[str], cap: int) -> list[str]:
    """The waiting claims a run that started these should still have worked:
    those it tried that went back in the queue, and new ones while it's under
    its cap."""
    waiting = [c["claim_id"] for c in waiting_claims()]
    tried_again = [c for c in waiting if c in started]
    new = [c for c in waiting if c not in started][: cap - len(started)]
    return tried_again + new


def drive(
    agent: CompiledStateGraph[Any, Any, Any, Any],
    context: RunContext,
    started: list[str],
    ask: str,
    config: RunnableConfig,
) -> str:
    """Drive the queue agent through its run, which fills in the claims it
    started, remind it once of any claims it missed, and return its summary,
    with any claims still missed after that."""
    config = {**config, "run_name": "queue-agent"}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": ask}]},
        context=context,
        config=config,
    )
    still_waiting = missed(started, context.cap)
    if still_waiting:
        reminder = MISSED.format(claims=", ".join(still_waiting))
        messages = [*result["messages"], {"role": "user", "content": reminder}]
        result = agent.invoke({"messages": messages}, context=context, config=config)
    summary = str(result["messages"][-1].text)
    still_waiting = missed(started, context.cap)
    if still_waiting:
        summary += "\n\n" + LEFT_WAITING.format(claims=", ".join(still_waiting))
    return summary


def run_queue(
    cap: int,
    model: Model,
    llm: BaseChatModel | None = None,
    claim_llm: BaseChatModel | None = None,
) -> str:
    """Work up to `cap` waiting claims with the queue agent, each by a claim agent
    of its own, one at a time, and return the summary the run finished with. The
    run is one `run-queue` trace; each claim's work is a trace of its own, in the
    claim's session. The run is finished whatever happens, with what stopped it
    if something did."""
    agent = queue_agent(llm or chat_model(model), model, cap)
    run_id = api.start_run("queue", cap, model.spec)["run_id"]
    one_at_a_time = threading.Lock()
    started: list[str] = []

    def work(claim_id: str) -> str:
        with one_at_a_time:
            report = work_claim(claim_id, run_id, model, claim_llm)
            if claim_id not in started:
                started.append(claim_id)
            return report

    context = RunContext(run_id=run_id, cap=cap, work=work)
    ask = f"Work up to {cap} waiting claims in this run."
    try:
        summary = tracing.traced(
            "run-queue",
            ask,
            lambda config: drive(agent, context, started, ask, config),
            run_id=str(run_id),
            model=model.spec,
        )
    except Exception as error:
        api.finish_run(run_id, f"The run stopped: {type(error).__name__}: {error}")
        raise
    api.finish_run(run_id, summary)
    return summary
