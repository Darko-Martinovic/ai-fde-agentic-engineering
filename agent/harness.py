"""Builds and runs the UnderCover Agent: its model, the middleware around it,
and its runs."""

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
from langgraph.graph.state import CompiledStateGraph

from agent import api
from agent.config import Model
from agent.middleware import StepRecorder, UsageRecorder, refusal
from agent.tools import CLAIM_TOOLS, ClaimContext
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
STOPPED = (
    "The agent stopped before finishing the claim, having replied without a"
    f" decision or reached its limit of {MAX_MODEL_CALLS} model calls"
)

# Our providers, and the LangChain integration that serves each one
INTEGRATIONS = {"openrouter": "openai", "anthropic": "anthropic", "ollama": "ollama"}

# How to reach each provider, from the settings
CONNECTIONS: dict[str, Callable[[], dict[str, Any]]] = {
    "openrouter": lambda: {
        "base_url": setting("OPENROUTER_BASE_URL"),
        "api_key": setting("OPENROUTER_API_KEY"),
    },
    "anthropic": lambda: {"api_key": setting("ANTHROPIC_API_KEY")},
    "ollama": lambda: {
        "base_url": setting("OLLAMA_BASE_URL"),
        "num_ctx": int(setting("OLLAMA_NUM_CTX")),
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
    """The agent's instructions and the documents' contents, both from the API."""
    return f"{api.get_instructions()}\n\n{contents()}"


def claim_agent(
    llm: BaseChatModel, model: Model
) -> CompiledStateGraph[Any, Any, Any, Any]:
    middleware: list[AgentMiddleware[Any, Any]] = [
        UsageRecorder(model),
        ModelRetryMiddleware(
            max_retries=MODEL_RETRIES, on_failure="error", initial_delay=RETRY_DELAY
        ),
        ModelCallLimitMiddleware(run_limit=MAX_MODEL_CALLS, exit_behavior="end"),
        StepRecorder(),
        ToolErrorMiddleware(refusal),
    ]
    return create_agent(
        llm,
        tools=CLAIM_TOOLS,
        system_prompt=instructions(),
        context_schema=ClaimContext,
        middleware=middleware,
    )


def report(claim: dict[str, Any]) -> str:
    """The line a claim's work reports: its outcome, from the backend's record."""
    claim_id, status = claim["claim_id"], claim["status"]
    decision = claim["decisions"][-1] if claim["decisions"] else None
    if decision is None or status == "left_for_handler":
        return f"{claim_id}: {BY_STATE[status]}"
    if decision["decision"] != "approve":
        return f"{claim_id}: {BY_DECISION[decision['decision']]}"
    return f"{claim_id}: approved ${decision['payout']:,.2f}, {BY_STATE[status]}"


def failed(context: ClaimContext, reason: str) -> str:
    """Record that work on a claim failed before it was decided, and report where
    the claim now stands. A failure after the decision changes nothing."""
    claim = api.get_claim(context.claim_id)
    if claim["status"] != "in_progress":
        return f"{report(claim)} (then {reason})"
    claim = api.fail_claim(context.claim_id, context.thread_id, reason)
    return f"{report(claim)} ({reason})"


def work_claim(
    claim_id: str, run_id: int, model: Model, llm: BaseChatModel | None = None
) -> str:
    """Work one claim in a run from a clean start, and report in a line: the
    decision and payout, or what went wrong."""
    context = ClaimContext(
        run_id=run_id, claim_id=claim_id, thread_id=f"{claim_id}-{uuid4().hex[:8]}"
    )
    agent = claim_agent(llm or chat_model(model), model)
    api.start_claim(claim_id, run_id, context.thread_id)
    try:
        agent.invoke(
            {"messages": [{"role": "user", "content": f"Claim {claim_id}"}]},
            context=context,
        )
    except Exception as error:  # noqa: BLE001 - one bad claim never stops a run
        return failed(context, f"{type(error).__name__}: {error}")
    if api.get_claim(claim_id)["status"] == "in_progress":
        return failed(context, STOPPED)
    return report(api.get_claim(claim_id))
