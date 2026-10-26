"""What happens around the queue agent's model and tool calls: recording each
model call's usage on the run, and giving the backend's refusals back to the
model as text. The claim agent is a graph of our own, whose nodes do this."""

import time
from collections.abc import Callable
from typing import Any, cast

from langchain.agents import AgentState
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
)
from langchain_core.messages import AIMessage

from agent import api, recording
from agent.config import Model
from agent.tools import RunScope


class UsageRecorder(AgentMiddleware[AgentState[Any], Any]):
    """Record each model call's tokens, cost and time on its run."""

    def __init__(self, model: Model) -> None:
        super().__init__()
        self.model = model

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        started = time.monotonic()
        response = handler(request)
        seconds = time.monotonic() - started
        replies = [m for m in response.result if isinstance(m, AIMessage)]
        context = cast(RunScope, request.runtime.context)
        recording.usage(context, self.model, replies[0] if replies else None, seconds)
        return response


def refusal(error: Exception, request: ToolCallRequest) -> str | None:
    """Give the backend's refusal back to the model as text. Anything else stops
    the run."""
    return str(error) if isinstance(error, api.Refused) else None
