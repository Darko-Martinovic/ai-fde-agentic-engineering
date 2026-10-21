"""What happens around the agents' model and tool calls: recording the steps on
the claim, recording each model call's usage on the run, and giving the
backend's refusals back to the model as text."""

import json
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
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command

from agent import api
from agent.config import Model
from agent.tools import ClaimContext, RunScope, read_section


def steps(message: AIMessage) -> list[tuple[str, str]]:
    """Turn one reply from the model into the steps the dashboard shows."""
    found = [("reply", str(message.text))] if message.text else []
    return found + [
        ("tool_call", f"{call['name']} {json.dumps(call['args'], ensure_ascii=False)}")
        for call in message.tool_calls
    ]


def section_read(result: str) -> str:
    """The step for a section the agent read: the backend's section, less its text."""
    section = json.loads(result)
    del section["text"]
    return json.dumps(section)


def record(context: ClaimContext, kind: str, text: str) -> None:
    api.record_step(context.claim_id, context.thread_id, kind, text)


class StepRecorder(AgentMiddleware[AgentState[Any], ClaimContext]):
    """Record every reply, tool call and tool result on the claim being worked."""

    def after_model(
        self, state: AgentState[Any], runtime: Runtime[ClaimContext]
    ) -> dict[str, Any] | None:
        message = state["messages"][-1]
        if isinstance(message, AIMessage):
            for kind, text in steps(message):
                record(runtime.context, kind, text)
        return None

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        result = handler(request)
        if isinstance(result, ToolMessage):
            context = cast(ClaimContext, request.runtime.context)
            record(context, "tool_result", str(result.text))
            if (
                request.tool_call["name"] == read_section.name
                and result.status != "error"
            ):
                record(context, "section", section_read(str(result.text)))
        return result


class UsageRecorder(AgentMiddleware[AgentState[Any], Any]):
    """Record each model call's tokens, cost and time on its run, and on its claim
    when a claim agent made it."""

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
        context = cast(RunScope, request.runtime.context)
        claim_id = context.claim_id if isinstance(context, ClaimContext) else None
        replies = [m for m in response.result if isinstance(m, AIMessage)]
        usage = (replies[0].usage_metadata if replies else None) or {}
        tokens_in = usage.get("input_tokens", 0)
        tokens_out = usage.get("output_tokens", 0)
        api.record_usage(
            context.run_id,
            {
                "claim_id": claim_id,
                "model": self.model.spec,
                "input_tokens": tokens_in,
                "output_tokens": tokens_out,
                "cost": self.model.cost(tokens_in, tokens_out),
                "seconds": seconds,
            },
        )
        return response


def refusal(error: Exception, request: ToolCallRequest) -> str | None:
    """Give the backend's refusal back to the model as text. Anything else stops
    the run."""
    return str(error) if isinstance(error, api.Refused) else None
