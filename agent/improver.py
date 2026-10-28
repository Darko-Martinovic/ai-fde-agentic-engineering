"""The improver: a LangChain agent, as in labs/week2day5.ipynb, that improves
the claim agent's configuration by following its recipe, with the lab's four
tools. A handler reviews each proposal: `HumanInTheLoopMiddleware` pauses the
improver until one approves or rejects it, and the agent's service records the
proposal and the review. The backend records what an approval makes and keeps
or rolls back the version tried. The improver reaches the claim agents only
through the function the service hands it, to work an evaluation."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import Any, cast

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    HumanInTheLoopMiddleware,
    InterruptOnConfig,
    ModelCallLimitMiddleware,
    ModelRequest,
    ModelResponse,
    before_model,
    wrap_model_call,
)
from langchain.agents.middleware.types import ToolCallRequest
from langchain.tools import ToolRuntime, tool
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command

from agent import improver_api
from agent.connection import Refused
from agent.recording import cost, tokens

# The most model calls the improver makes in a round, across its pauses
IMPROVER_CALLS = 20
PROPOSALS = ("propose_change", "propose_recipe")
# A version is evaluated once on the evaluation set and twice on the held-out set
EVALUATIONS = ("evaluation", "held_out", "held_out")
FIRST_MESSAGE = "Please carry out one round of your recipe."
# How each provider is asked for one tool call at a time: OpenRouter takes
# OpenAI's setting; Ollama refuses it, so it's asked nothing
ONE_CALL_AT_A_TIME: dict[str, dict[str, Any]] = {
    "openrouter": {"parallel_tool_calls": False}
}
OPEN = "open"


@dataclass(frozen=True)
class RoundContext:
    """What the improver's tools and middleware know: the round, the model the
    improver runs on, the models a change may use, and how to work one of the
    round's evaluations, which the service hands it."""

    round_id: int
    model: str
    provider: str
    models_allowed: list[dict[str, Any]]
    evaluate: Callable[[dict[str, Any]], None]


def allowed(models: list[dict[str, Any]], model: str, reasoning_effort: str) -> bool:
    """Whether a change may use a model at a reasoning effort: the check the
    tool and the review's predicate share, as the backend makes it too."""
    return any(
        m["model"] == model and reasoning_effort in m["reasoning_efforts"]
        for m in models
    )


def not_allowed(model: str, reasoning_effort: str) -> str:
    return (
        f"{model} at {reasoning_effort} isn't allowed. Choose from the models allowed."
    )


@tool
def read_results(runtime: ToolRuntime[RoundContext]) -> str:
    """Read the current version of the claim agent's configuration, its scores,
    its mistakes and weakest explanations on the evaluation set, the earlier
    rounds, the objectives, the spending limit left and the models allowed."""
    view = improver_api.get_improver_view(runtime.context.round_id)
    return json.dumps(view, indent=2)


@tool(parse_docstring=True)
def propose_change(
    instructions: str,
    model: str,
    reasoning_effort: str,
    reason: str,
    runtime: ToolRuntime[RoundContext],
) -> str:
    """Propose a new version of the claim agent's configuration. A handler
    reviews it before it's saved.

    Args:
        instructions: The claim agent's complete instructions
        model: One of the models allowed
        reasoning_effort: A reasoning level allowed for that model
        reason: Why this change should improve the scores
    """
    if not allowed(runtime.context.models_allowed, model, reasoning_effort):
        return not_allowed(model, reasoning_effort)
    made = improver_api.create_version(runtime.context.round_id)
    return f"Saved as version {made['version_tried']}. Run the evaluation next."


@tool
def run_evaluation(runtime: ToolRuntime[RoundContext]) -> str:
    """Run the newest version once on the evaluation set and twice on the
    held-out set, then keep it or roll it back."""
    context = runtime.context
    worked = improver_api.get_round(context.round_id)
    if worked["version_tried"] is None or worked["verdict"] is not None:
        return "There's no new version to evaluate. Propose a change first."
    refusal = ""
    try:
        for evaluation_set in EVALUATIONS:
            run = improver_api.create_round_evaluation(context.round_id, evaluation_set)
            context.evaluate(run)
    except Refused as refused:
        refusal = f"Refused: {refused.detail}\n"
    try:
        verdict = improver_api.record_verdict(context.round_id)
    except Refused as refused:
        return f"{refusal}Refused: {refused.detail}"
    kept = "Kept" if verdict["kept"] else "Rolled back"
    scores = {
        name: verdict[name]
        for name in ("held_out_before", "held_out_after", "evaluation_after")
    }
    return (
        f"{refusal}{kept} version {verdict['version']}: {verdict['why']}. Version"
        f" {verdict['current_version']} is now the current version.\n"
        f"{json.dumps(scores, indent=2)}"
    )


@tool(parse_docstring=True)
def propose_recipe(recipe: str, reason: str, runtime: ToolRuntime[RoundContext]) -> str:
    """Propose a new version of your recipe for improving the claim agent. A
    handler reviews it before it's saved.

    Args:
        recipe: The complete new recipe
        reason: What this round showed, and why the new recipe should lead to
            better changes
    """
    made = improver_api.create_recipe(runtime.context.round_id)
    return f"Saved as recipe version {made['number']}."


TOOLS = [read_results, propose_change, run_evaluation, propose_recipe]


def needs_review(request: ToolCallRequest) -> bool:
    """Whether a proposal goes to a handler: all of them, but a change to a
    model not allowed, which the tool answers without recording anything."""
    call = request.tool_call
    if call["name"] != "propose_change":
        return True
    context = cast(RoundContext, request.runtime.context)
    args = call["args"]
    return allowed(
        context.models_allowed, args.get("model", ""), args.get("reasoning_effort", "")
    )


@before_model(can_jump_to=["end"])
def end_when_the_round_ends(
    state: AgentState[Any], runtime: Runtime[RoundContext]
) -> dict[str, Any] | None:
    """End the stretch before the next model call once the round has ended, as
    when a handler stops it."""
    if improver_api.get_round(runtime.context.round_id)["status"] != OPEN:
        return {"jump_to": "end"}
    return None


@wrap_model_call
def one_call_recorded(
    request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
) -> ModelResponse:
    """Ask for one tool call at a time, as the recipe's steps follow each other,
    and record each model call's tokens, cost and time with the round."""
    context = cast(RoundContext, request.runtime.context)
    settings = request.model_settings | ONE_CALL_AT_A_TIME.get(context.provider, {})
    started = monotonic()
    response = handler(request.override(model_settings=settings))
    seconds = monotonic() - started
    message = next(m for m in response.result if isinstance(m, AIMessage))
    tokens_in, tokens_out = tokens(message)
    improver_api.record_improver_call(
        context.round_id,
        {
            "model": context.model,
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "cost": cost(message),
            "seconds": seconds,
        },
    )
    return response


def improver(
    llm: BaseChatModel, instructions: str, saver: BaseCheckpointSaver[Any]
) -> CompiledStateGraph[Any, RoundContext, Any, Any]:
    """The improver, with its instructions and recipe, saving its progress on
    the round's thread with `saver`, so a pause for a handler survives a
    restart."""
    review = InterruptOnConfig(
        allowed_decisions=["approve", "reject"], when=needs_review
    )
    middleware: list[AgentMiddleware[Any, Any, Any]] = [
        HumanInTheLoopMiddleware(interrupt_on=dict.fromkeys(PROPOSALS, review)),
        ModelCallLimitMiddleware(thread_limit=IMPROVER_CALLS, exit_behavior="error"),
        end_when_the_round_ends,
        one_call_recorded,
    ]
    return create_agent(
        model=llm,
        tools=TOOLS,
        system_prompt=instructions,
        middleware=middleware,
        context_schema=RoundContext,
        checkpointer=saver,
        name="improver",
    )


def resume(approved: bool, note: str) -> Command[Any]:
    """Carry the improver on past a handler's review: an approval, or a
    rejection whose reason the improver reads as the tool's answer."""
    if approved:
        return Command(resume={"decisions": [{"type": "approve"}]})
    return Command(resume={"decisions": [{"type": "reject", "message": note}]})


def work_stretch(
    agent: CompiledStateGraph[Any, RoundContext, Any, Any],
    context: RoundContext,
    thread_id: str,
    start: Command[Any] | None,
    config: RunnableConfig,
) -> dict[str, Any] | None:
    """Run the improver on the round's thread, from its first message or past
    a review, until it pauses for a handler, returning the proposal it waits
    on, or ends, returning none."""
    finished = agent.invoke(
        start or {"messages": [{"role": "user", "content": FIRST_MESSAGE}]},
        context=context,
        config={
            **config,
            "run_name": "improver",
            "configurable": {"thread_id": thread_id},
        },
        durability="sync",
    )
    paused = finished.get("__interrupt__")
    return paused[0].value["action_requests"][0] if paused else None
