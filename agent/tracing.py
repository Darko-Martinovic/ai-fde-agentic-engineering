"""Tracing the claim agents and the improver in Langfuse. Each piece of work on
a claim is a trace of its own, in the session named after the claim's thread,
so everything that happens on one claim, before and after a pause or a
restart, is found together, and each one in a run is tagged with the run, and
with its round when the run is one of a round's evaluations. Each stretch of
the improver's work is a trace in its round's session, tagged with the round. Langfuse's
address and environment come from the settings; it reads its keys from the
environment, which the settings fill in from .env. Without the keys nothing is
sent, and Langfuse warns that it's off."""

import contextvars
from collections.abc import Callable
from contextvars import ContextVar

from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse, propagate_attributes
from langfuse.langchain import CallbackHandler

from settings import setting

# The tags a run's claims are traced with besides the run's own, as a round's
# evaluations are tagged with the round. The dispatcher sets them for its run.
RUN_TAGS: ContextVar[tuple[str, ...]] = ContextVar("run_tags", default=())


def client() -> Langfuse:
    """The Langfuse client. Langfuse keeps one for each key, so the first one
    made sets it up, and the agents' callbacks find the same one. It sends what's
    left when the process ends."""
    return Langfuse(
        base_url=setting("LANGFUSE_BASE_URL"),
        environment=setting("LANGFUSE_TRACING_ENVIRONMENT"),
    )


def traced(
    name: str,
    request: str,
    work: Callable[[RunnableConfig], str],
    **metadata: str,
) -> str:
    """Do `work` in a trace named `name`, which reads as the request and the line
    `work` reports. `work` passes the config it's given to its agent, which puts
    the agent's model and tool calls in the trace."""
    with (
        client().start_as_current_observation(name=name, input=request) as span,
        propagate_attributes(trace_name=name, metadata=metadata),
    ):
        report = work({"callbacks": [CallbackHandler()]})
        span.update(output=report)
    return report


def claim_trace(
    name: str,
    claim_id: str,
    thread_id: str,
    work: Callable[[RunnableConfig], str],
    run_id: int | None,
    **metadata: str,
) -> str:
    """Do `work` on one claim in a trace named `name`, in the claim's session,
    named after its thread. A claim worked in a run is tagged with the run, and
    with the run's tags, so a whole run's claims are found together. It runs in
    a fresh context, so the trace is one of its own, and the claim graph is
    never taken for a subgraph of the dispatcher that works it."""
    if run_id is not None:
        metadata = metadata | {"run_id": str(run_id)}
        work = tagged(work, f"run-{run_id}", *RUN_TAGS.get())

    def in_session() -> str:
        with propagate_attributes(session_id=thread_id):
            return traced(
                name, claim_id, work, claim_id=claim_id, thread_id=thread_id, **metadata
            )

    return contextvars.Context().run(in_session)


def tagged[T](
    work: Callable[[RunnableConfig], T], *tags: str
) -> Callable[[RunnableConfig], T]:
    """`work`, with Langfuse's tags in the metadata of the config it's given,
    which the agent's root run puts on its trace."""
    return lambda config: work(
        {
            **config,
            "metadata": {**config.get("metadata", {}), "langfuse_tags": list(tags)},
        }
    )


def round_trace[T](
    round_id: int, thread_id: str, work: Callable[[RunnableConfig], T]
) -> T:
    """Do a stretch of the improver's work in a trace of its own, in the round's
    session, named after its thread, tagged with the round. It runs in a fresh
    context, so the trace is one of its own."""
    tag = f"round-{round_id}"

    def in_session() -> T:
        with (
            propagate_attributes(session_id=thread_id),
            client().start_as_current_observation(name="improver", input=tag),
            propagate_attributes(
                trace_name="improver", metadata={"round_id": str(round_id)}
            ),
        ):
            return tagged(work, tag)({"callbacks": [CallbackHandler()]})

    return contextvars.Context().run(in_session)
