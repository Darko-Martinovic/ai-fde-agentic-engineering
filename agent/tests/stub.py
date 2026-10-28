from collections.abc import Iterator

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from agent.versions import Model, Version

# A version of the claim agent to work claims as in tests, on a free model the
# tests never call
FREE = Version(
    number=1,
    instructions="# UnderCover claim agent\n\nDecide the claim.",
    model=Model(name="openrouter/free", provider="openrouter", options={}),
)


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


# The reasons every decision in the tests gives
REASONS = "The delay was covered and the costs were reasonable."


def decide(decision, payout):
    """A reply that decides the claim, against the Trip Delay section."""
    return tool_call(
        "decide_claim",
        decision=decision,
        payout=payout,
        reasons=REASONS,
        policy_section="Section 3, Trip Delay",
    )


class ByClaim(StubModel):
    """A stub model for claim agents working side by side: each claim's replies
    come from its own script, chosen by the claim its thread starts with."""

    scripts: dict[str, Iterator[AIMessage]]

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        first = next(m for m in messages if isinstance(m, HumanMessage))
        claim_id = str(first.content).removeprefix("Claim ")
        return ChatResult(generations=[ChatGeneration(message=self.reply(claim_id))])

    def reply(self, claim_id):
        return next(self.scripts[claim_id])


def by_claim(**scripts):
    """A stub model that works each claim named, as CLM_1001=[replies], from its
    own replies."""
    return ByClaim(
        messages=iter([]),
        scripts={
            claim.replace("_", "-"): iter(replies) for claim, replies in scripts.items()
        },
    )
