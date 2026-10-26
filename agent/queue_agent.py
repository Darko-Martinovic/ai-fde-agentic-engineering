"""The queue agent, which works a run of the queue on LangChain's create_agent:
the middleware around it, and its run, handing each claim to a claim agent."""

import threading
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    ToolErrorMiddleware,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from agent import api, config, tracing
from agent.config import Model
from agent.harness import chat_model, work_claim
from agent.middleware import UsageRecorder, refusal
from agent.tools import QUEUE_TOOLS, RunContext, waiting_claims

# The queue agent's model calls: a few for each claim, and some to plan and sum up
QUEUE_CALLS_A_CLAIM = 4
QUEUE_CALLS = 10
MISSED = (
    "Before you finish: these claims are still waiting, and this run should work"
    " them: {claims}. Work them, update your to-do list, then give your summary."
)
LEFT_WAITING = "Still waiting, though this run should have worked them: {claims}."


def middleware(model: Model, model_calls: int) -> list[AgentMiddleware[Any, Any]]:
    """What the queue agent has around its calls: usage recorded, provider errors
    retried, its model calls capped and refusals given back as text."""
    return [
        UsageRecorder(model),
        ModelRetryMiddleware(
            max_retries=config.MODEL_RETRIES,
            on_failure="error",
            initial_delay=config.RETRY_DELAY,
        ),
        ModelCallLimitMiddleware(run_limit=model_calls, exit_behavior="end"),
        ToolErrorMiddleware(refusal),
    ]


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
    saver: BaseCheckpointSaver[Any],
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
            report = work_claim(claim_id, run_id, model, saver, claim_llm)
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
