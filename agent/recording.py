"""What the agents record on the backend as they work: each reply, tool call,
tool result and section read as a step on the claim; each claim agent's model
call, with its tokens, cost and time, and each spell of its work, on the claim,
with its run; and each of the queue agent's model calls on its run."""

import json

from langchain_core.messages import AIMessage, ToolMessage

from agent import api
from agent.config import Model
from agent.tools import ClaimContext, RunContext


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


def tokens(message: AIMessage | None) -> tuple[int, int]:
    """A reply's input and output tokens, or none when the call gave no reply."""
    used = (message.usage_metadata if message else None) or {}
    return used.get("input_tokens", 0), used.get("output_tokens", 0)


def cost(model: Model, message: AIMessage) -> float:
    """What a model call cost in US dollars: as the provider reports it, as
    OpenRouter does, or else at the model's prices in models.toml."""
    reported = (message.response_metadata.get("token_usage") or {}).get("cost")
    return float(reported) if reported is not None else model.cost(*tokens(message))


def model_call(
    context: ClaimContext, model: Model, message: AIMessage, seconds: float
) -> None:
    """Record one of a claim agent's model calls on the claim, with its run."""
    tokens_in, tokens_out = tokens(message)
    api.record_model_call(
        context.claim_id,
        {
            "thread_id": context.thread_id,
            "run_id": context.run_id,
            "model": model.spec,
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "cost": cost(model, message),
            "seconds": seconds,
        },
    )


def work_time(context: ClaimContext, seconds: float) -> None:
    """Record one spell of a claim agent's work on the claim, with its run."""
    api.record_work_time(
        context.claim_id,
        {"thread_id": context.thread_id, "run_id": context.run_id, "seconds": seconds},
    )


def usage(
    context: RunContext, model: Model, message: AIMessage | None, seconds: float
) -> None:
    """Record one of the queue agent's model calls on its run."""
    tokens_in, tokens_out = tokens(message)
    api.record_usage(
        context.run_id,
        {
            "claim_id": None,
            "model": model.spec,
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "cost": model.cost(tokens_in, tokens_out),
            "seconds": seconds,
        },
    )
