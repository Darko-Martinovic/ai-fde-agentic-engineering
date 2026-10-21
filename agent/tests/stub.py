from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent.config import model

# A model to work claims on in tests, which never call it
FREE = model("openrouter:openrouter/free")


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def stub(*replies):
    """A stub model that gives these replies, in order."""
    return StubModel(messages=iter(replies))


def call(name, **args):
    """One tool call, for `calls`."""
    return {"name": name, "args": args, "id": f"call-{name}-{len(str(args))}"}


def calls(*tool_calls):
    """A reply that makes these tool calls, all at once."""
    return AIMessage(content="", tool_calls=list(tool_calls))


def tool_call(name, **args):
    """A reply that makes one tool call."""
    return calls(call(name, **args))


def decide(decision, payout):
    """A reply that decides the claim, against the Trip Delay section."""
    return tool_call(
        "decide_claim",
        decision=decision,
        payout=payout,
        reasons="The delay was covered and the costs were reasonable.",
        policy_section="Section 3, Trip Delay",
    )
