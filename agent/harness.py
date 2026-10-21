"""Builds and runs the UnderCover Agent: its model, its middleware and its runs."""

import json
from collections.abc import Callable
from typing import Any, cast
from uuid import uuid4

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ToolCallRequest,
    ToolErrorMiddleware,
)
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command

from agent import api
from agent.config import Model, current_model, setting
from agent.tools import CLAIM_TOOLS, ClaimContext

# Our providers, and the LangChain integration that serves each one
INTEGRATIONS = {"openrouter": "openai", "anthropic": "anthropic", "ollama": "ollama"}


def connection(provider: str) -> dict[str, Any]:
    """How to reach a provider, from the settings."""
    if provider == "openrouter":
        return {
            "base_url": setting("OPENROUTER_BASE_URL"),
            "api_key": setting("OPENROUTER_API_KEY"),
        }
    if provider == "anthropic":
        return {"api_key": setting("ANTHROPIC_API_KEY")}
    return {
        "base_url": setting("OLLAMA_BASE_URL"),
        "num_ctx": int(setting("OLLAMA_NUM_CTX")),
    }


def chat_model(model: Model) -> BaseChatModel:
    """Build the chat model for one of the models allowed."""
    return init_chat_model(
        model.name,
        model_provider=INTEGRATIONS[model.provider],
        **connection(model.provider),
        **model.options,
    )


def steps(message: AIMessage) -> list[tuple[str, str]]:
    """Turn one reply from the model into the steps the dashboard shows."""
    found = [("reply", str(message.text))] if message.text else []
    return found + [
        ("tool_call", f"{call['name']} {json.dumps(call['args'], ensure_ascii=False)}")
        for call in message.tool_calls
    ]


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
        return result


def record(context: ClaimContext, kind: str, text: str) -> None:
    api.record_step(context.claim_id, context.thread_id, kind, text)


def refusal(error: Exception, request: ToolCallRequest) -> str | None:
    """Give the backend's refusal back to the model as text. Anything else stops
    the run."""
    return str(error) if isinstance(error, api.Refused) else None


def instructions() -> str:
    """Join the agent's instructions and the policy wording, both from the API."""
    return f"{api.get_instructions()}\n\n{api.get_policy_wording()}"


def claim_agent(llm: BaseChatModel):
    return create_agent(
        llm,
        tools=CLAIM_TOOLS,
        system_prompt=instructions(),
        context_schema=ClaimContext,
        middleware=[StepRecorder(), ToolErrorMiddleware(refusal)],
    )


def work_claim(claim_id: str, llm: BaseChatModel | None = None) -> str:
    """Work one claim from a clean start, and return the agent's last reply."""
    api.start_claim(claim_id)
    context = ClaimContext(claim_id, f"{claim_id}-{uuid4().hex[:8]}")
    agent = claim_agent(llm or chat_model(current_model()))
    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"Claim {claim_id}"}]},
        context=context,
    )
    return result["messages"][-1].text
