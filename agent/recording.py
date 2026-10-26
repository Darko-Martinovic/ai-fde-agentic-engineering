"""What the agents record on the backend as they work: each reply, tool call,
tool result and section read as a step on the claim, and each model call's
tokens, cost and time on the run."""

import json

from langchain_core.messages import AIMessage, ToolMessage

from agent import api
from agent.config import Model
from agent.tools import ClaimContext, RunScope


def steps(message: AIMessage) -> list[tuple[str, str]]:
    """Turn one reply from the model into the steps the dashboard shows."""
    found = [("reply", str(message.text))] if message.text else []
    return found + [
        ("tool_call", f"{call['name']} {json.dumps(call['args'], ensure_ascii=False)}")
        for call in message.tool_calls
    ]


def record(context: ClaimContext, kind: str, text: str) -> None:
    api.record_step(context.claim_id, context.thread_id, kind, text)


def reply(context: ClaimContext, message: AIMessage) -> None:
    """Record a reply from the model, and the tools it calls, on the claim."""
    for kind, text in steps(message):
        record(context, kind, text)


def tool_result(context: ClaimContext, message: ToolMessage) -> None:
    record(context, "tool_result", str(message.text))


def section(context: ClaimContext, result: str) -> None:
    """Record a section the agent read: the backend's section, less its text."""
    read = json.loads(result)
    del read["text"]
    record(context, "section", json.dumps(read))


def usage(
    scope: RunScope, model: Model, message: AIMessage | None, seconds: float
) -> None:
    """Record one model call's tokens, cost and time on its run, and on its claim
    when a claim agent made it."""
    used = (message.usage_metadata if message else None) or {}
    tokens_in = used.get("input_tokens", 0)
    tokens_out = used.get("output_tokens", 0)
    api.record_usage(
        scope.run_id,
        {
            "claim_id": scope.claim_id if isinstance(scope, ClaimContext) else None,
            "model": model.spec,
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "cost": model.cost(tokens_in, tokens_out),
            "seconds": seconds,
        },
    )
