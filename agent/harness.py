"""Builds and runs the claim agents, each from a version of the claim agent's
configuration: the model, the claim graph for each claim, and its work on the
claim, reported in a line."""

from collections.abc import Callable
from time import monotonic
from typing import Any
from uuid import uuid4

from langchain.chat_models import init_chat_model
from langchain_core.exceptions import ModelRateLimitError, ModelTimeoutError
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command

from agent import api, graph, recording, tracing, versions
from agent.reports import AWAITING_SIGN_OFF, IN_PROGRESS, report
from agent.tools import ClaimContext
from agent.versions import Model, Version
from settings import setting

STOPPED = "The agent stopped before finishing the claim: it replied with no decision"
# The model errors that pass with time. Work on a claim that hits one stops
# without settling the claim, which stays in progress, its progress saved, for
# the dispatcher to carry on after a wait.
TRANSIENT = (ModelRateLimitError, ModelTimeoutError)

# Our providers, and the LangChain integration that serves each one: the
# models allowed are on OpenRouter, and a free model in MODEL_NAME may be on
# OpenRouter or a local Ollama
INTEGRATIONS = {"openrouter": "openai", "ollama": "ollama"}


def timeout() -> float:
    return float(setting("MODEL_TIMEOUT"))


# How to reach each provider, from the settings. A call fails when the provider
# sends nothing for MODEL_TIMEOUT seconds, which doesn't bound a reply that
# keeps coming (data/models.json caps a reply's tokens for that), and only the claim
# graph's model retries it, not the provider's client.
CONNECTIONS: dict[str, Callable[[], dict[str, Any]]] = {
    "openrouter": lambda: {
        "base_url": setting("OPENROUTER_BASE_URL"),
        "api_key": setting("OPENROUTER_API_KEY"),
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
    """Build the chat model a version runs on, at its reasoning effort."""
    return init_chat_model(
        model.name,
        model_provider=INTEGRATIONS[model.provider],
        **CONNECTIONS[model.provider](),
        **model.build_options,
    )


def contents() -> str:
    """List the sections of the wording and the manual, for the agent to look up."""
    lines = [
        f"- {s['document_title']} {s['number']}. {s['title']}"
        for s in api.list_sections()
    ]
    return "## The sections you can read\n\n" + "\n".join(lines)


def instructions(version: Version) -> str:
    """A version's instructions, and the documents' contents from the API."""
    return f"{version.instructions}\n\n{contents()}"


def current_version() -> Version:
    """The current version of the claim agent's configuration."""
    return versions.version(api.get_current_version())


def claim_graph(
    version: Version, saver: BaseCheckpointSaver[Any], llm: BaseChatModel | None = None
) -> graph.ClaimGraph:
    """The claim graph as a version builds it, saving its progress with `saver`."""
    return graph.claim_graph(
        llm or chat_model(version.model), version.model, saver, instructions(version)
    )


def undecided(claim: dict[str, Any]) -> bool:
    """Whether a claim in progress waits for the agent's decision: it has none,
    or a handler rejected the payout it had."""
    latest = claim["decisions"][-1] if claim["decisions"] else None
    in_progress = claim["status"] == IN_PROGRESS
    return in_progress and (latest is None or latest["review"] == "rejected")


def failed(context: ClaimContext, reason: str) -> str:
    """Record that work on a claim failed before it was decided, and report where
    the claim now stands. A failure after the decision changes nothing: the next
    run carries the claim on."""
    claim = api.get_claim(context.claim_id)
    if not undecided(claim):
        return f"{report(claim)} (then {reason})"
    claim = api.fail_claim(context.claim_id, context.thread_id, reason)
    return f"{report(claim)} ({reason})"


def work_one_spell(
    claim_graph: graph.ClaimGraph,
    context: ClaimContext,
    start: dict[str, Any] | Command[Any] | None,
    config: RunnableConfig,
) -> None:
    """Run the claim graph on the claim's thread, saving each step before the
    next, until it ends or pauses for a handler: one spell of work, whose time is
    recorded however it ends, so a wait for a handler never counts. A process
    that is killed records nothing, and should the recording fail, its error
    stands in for the graph's."""
    claim = {"claim_id": context.claim_id, "thread_id": context.thread_id}
    started = monotonic()
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
    finally:
        recording.work_time(context, monotonic() - started)


def run_graph(
    claim_graph: graph.ClaimGraph,
    context: ClaimContext,
    start: dict[str, Any] | Command[Any] | None,
    config: RunnableConfig,
) -> str:
    """Work the claim for a spell and report in a line: the decision and payout,
    or what went wrong, failing a claim left undecided. A transient error is
    raised again, leaving the claim in progress."""
    try:
        work_one_spell(claim_graph, context, start, config)
    except TRANSIENT:
        raise
    except Exception as error:  # noqa: BLE001 - one bad claim never stops a run
        return failed(context, f"{type(error).__name__}: {error}")
    worked = api.get_claim(context.claim_id)
    if undecided(worked):
        return failed(context, STOPPED)
    return report(worked)


def work_claim(
    claim_id: str,
    run_id: int | None,
    version: Version,
    saver: BaseCheckpointSaver[Any],
    llm: BaseChatModel | None = None,
) -> str:
    """Work one claim as a new attempt on a new thread, in a run or on its own
    (`run_id` None), in a trace of its own in the claim's session, and report in
    a line."""
    context = ClaimContext(
        run_id=run_id, claim_id=claim_id, thread_id=f"{claim_id}-{uuid4().hex[:8]}"
    )
    claim_graph_on_model = claim_graph(version, saver, llm)
    api.start_claim(claim_id, run_id, context.thread_id)
    return tracing.claim_trace(
        "work-claim",
        claim_id,
        context.thread_id,
        lambda config: run_graph(
            claim_graph_on_model, context, first_message(claim_id), config
        ),
        run_id,
        model=version.model.name,
    )


def first_message(claim_id: str) -> dict[str, Any]:
    """Where a claim's thread starts: the message naming the claim."""
    return {"messages": [HumanMessage(f"Claim {claim_id}")], "model_calls": 0}


def where_from(
    claim_graph: graph.ClaimGraph, claim: dict[str, Any], context: ClaimContext
) -> dict[str, Any] | Command[Any] | None:
    """Where a claim's thread carries on from: past a handler's review, with the
    review the backend holds; from the start if nothing was saved, as when the
    agent was stopped before its first step, and the claim has no decision; or
    from its last saved step."""
    saved = claim_graph.get_state({"configurable": {"thread_id": context.thread_id}})
    if "wait_for_sign_off" in saved.next:
        reviewed = claim["decisions"][-1]
        if reviewed["review"] is None:
            raise RuntimeError(f"{context.claim_id} waits for a handler's review")
        return Command(
            resume={
                "approved": reviewed["review"] == "signed_off",
                "note": reviewed["review_note"] or "",
            }
        )
    if saved.created_at is None and claim["decisions"]:
        # A decision the claim graph never saved, as one made through the API:
        # there's nothing to carry on, and starting afresh would decide it again
        raise RuntimeError(f"{context.claim_id} has no saved progress to carry on")
    if saved.created_at is None:
        return first_message(context.claim_id)
    return None


def carry_on(
    claim_id: str,
    run_id: int | None,
    version: Version,
    saver: BaseCheckpointSaver[Any],
    llm: BaseChatModel | None = None,
) -> str:
    """Carry a claim in progress on from its saved progress, on its latest
    attempt's thread, without a new attempt, in a trace of its own in the
    claim's session, and report in a line. Its model calls and its time count on
    `run_id`, or on no run when it's None, as after a handler's review. A
    claim that can't be picked up, as one whose decision the graph never saved,
    reports why and stays in progress, so it never stops a run."""
    try:
        claim = api.get_claim(claim_id)
        context = ClaimContext(
            run_id=run_id, claim_id=claim_id, thread_id=claim["thread_id"]
        )
        claim_graph_on_model = claim_graph(version, saver, llm)
        start = where_from(claim_graph_on_model, claim, context)
    except Exception as error:  # noqa: BLE001 - one claim never stops a run
        return f"{claim_id}: not picked up ({type(error).__name__}: {error})"
    return tracing.claim_trace(
        "carry-on",
        claim_id,
        context.thread_id,
        lambda config: run_graph(claim_graph_on_model, context, start, config),
        run_id,
        model=version.model.name,
    )


def work_in_run(
    claim_id: str,
    run_id: int | None,
    version: Version,
    new_saver: Callable[[], BaseCheckpointSaver[Any]],
    llm: BaseChatModel | None = None,
) -> str:
    """Work one claim in a run, or on its own (`run_id` None), with a saver of
    its own, and report in a line: carry it on if it's in progress, or start it
    if it's waiting, and for an evaluation's copy held for sign-off clear its
    saved progress. The one way a dispatch reaches the claim agent."""
    saver = new_saver()
    claim = api.get_claim(claim_id)
    work = carry_on if claim["status"] == IN_PROGRESS else work_claim
    report = work(claim_id, run_id, version, saver, llm)
    if claim["evaluation_id"] is not None:
        forget_held(claim_id, saver)
    return report


def forget_held(claim_id: str, saver: BaseCheckpointSaver[Any]) -> None:
    """Clear the saved progress of an evaluation's copy held for sign-off:
    nobody signs a copy off, so its approval counts as finished."""
    claim = api.get_claim(claim_id)
    if claim["status"] == AWAITING_SIGN_OFF:
        saver.delete_thread(claim["thread_id"])
