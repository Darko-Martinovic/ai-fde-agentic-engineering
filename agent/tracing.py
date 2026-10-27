"""Tracing the agents in Langfuse. Each piece of work on a claim is a trace of
its own, in the session named after the claim's thread, so everything that
happens on one claim, before and after a pause or a restart, is found together.
A queue run is one trace too, its tool calls handing claims on. Langfuse's
address and environment come from the settings; it reads its keys from the
environment, which the settings fill in from .env. Without the keys nothing is
sent, and Langfuse warns that it's off."""

import contextvars
from collections.abc import Callable

from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse, propagate_attributes
from langfuse.langchain import CallbackHandler
from langfuse.span_filter import is_default_export_span
from opentelemetry.sdk.trace import ReadableSpan

from settings import setting

# LangChain runs each middleware hook as a step of the agent's graph. Each would
# be an observation holding the whole conversation, showing nothing the model and
# tool calls around it don't, so none is sent.
HOOKS = (".before_agent", ".before_model", ".after_model", ".after_agent")


def sent(span: ReadableSpan) -> bool:
    """Whether a span goes to Langfuse: Langfuse's own choice, less the hooks."""
    return is_default_export_span(span) and not span.name.endswith(HOOKS)


def client() -> Langfuse:
    """The Langfuse client. Langfuse keeps one for each key, so the first one
    made sets it up, and the agents' callbacks find the same one. It sends what's
    left when the process ends, a run's process included."""
    return Langfuse(
        base_url=setting("LANGFUSE_BASE_URL"),
        environment=setting("LANGFUSE_TRACING_ENVIRONMENT"),
        should_export_span=sent,
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
    named after its thread. A claim worked in a run is tagged with the run, so a
    whole run's claims are found together. It runs in a fresh context, so the
    trace is one of its own even when a queue run's trace is current."""
    if run_id is not None:
        metadata = metadata | {"run_id": str(run_id)}
        work = tagged(work, f"run-{run_id}")

    def in_session() -> str:
        with propagate_attributes(session_id=thread_id):
            return traced(
                name, claim_id, work, claim_id=claim_id, thread_id=thread_id, **metadata
            )

    return contextvars.Context().run(in_session)


def tagged(
    work: Callable[[RunnableConfig], str], tag: str
) -> Callable[[RunnableConfig], str]:
    """`work`, with Langfuse's tag in the metadata of the config it's given,
    which the claim agent's root run puts on its trace."""
    return lambda config: work(
        {**config, "metadata": {**config.get("metadata", {}), "langfuse_tags": [tag]}}
    )
