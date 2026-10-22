"""Tracing the agents in Langfuse. A queue run is one trace, with each claim agent
it hands a claim to inside it, under the tool call that handed the claim on. A
run of claims named on the command line is a trace for each claim, the run's
traces sharing a session. Langfuse's address and environment come from the
settings; it reads its keys from the environment, which the settings fill in
from .env. Without the keys nothing is sent, and Langfuse warns that it's off."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from uuid import uuid4

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


@contextmanager
def session(run_id: int) -> Iterator[None]:
    """Put the traces made inside in one session, the run's. Run ids start again
    when the records are reseeded, so the session's name adds a few letters of
    its own."""
    with propagate_attributes(session_id=f"run-{run_id}-{uuid4().hex[:8]}"):
        yield


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
