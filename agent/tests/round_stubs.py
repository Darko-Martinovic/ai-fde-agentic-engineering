"""Stand-ins for a round of improvement's models: the improver's, giving
scripted replies and keeping what it was shown, and the claim agents', deciding
each copy in an evaluation by the claim it copies. Each call costs what
OpenRouter would report, so a round's spending adds up."""

from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from agent.tests.stub import StubModel, call
from backend import db
from backend.store import evaluations

IMPROVER_COST = 0.001
CLAIM_COST = 0.0001
USAGE = {"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100}


def costing(message: AIMessage, cost: float) -> AIMessage:
    """A reply with its tokens and its cost, as OpenRouter reports them."""
    return message.model_copy(
        update={
            "usage_metadata": USAGE,
            "response_metadata": {"token_usage": {"cost": cost}},
        }
    )


def says(name: str | None = None, **args: Any) -> AIMessage:
    """One of the improver's replies: a call of the tool named, or with no
    name, a last word and no call."""
    if name is None:
        return costing(AIMessage(content="That's the round done."), IMPROVER_COST)
    return costing(
        AIMessage(content="", tool_calls=[call(name, **args)]), IMPROVER_COST
    )


class Improver(StubModel):
    """The improver's model: its replies in order, and the messages it was
    shown for each."""

    shown: list[list[Any]] = Field(default_factory=list)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.shown.append(list(messages))
        return super()._generate(messages, stop, run_manager, **kwargs)


def improver(*replies: AIMessage) -> Improver:
    return Improver(messages=iter(replies))


def answer_key() -> dict[str, Any]:
    """The handlers' decisions on both sets, by the claim decided."""
    with db.engine().connect() as conn:
        return evaluations.handler_decisions(
            conn, "evaluation"
        ) | evaluations.handler_decisions(conn, "held_out")


def decision(decided: str, payout: float) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            call(
                "decide_claim",
                decision=decided,
                payout=payout,
                reasons="The wording settles it.",
                policy_section="Policy wording 3, Trip Delay",
            )
        ],
    )


def declines(claim_id: str) -> AIMessage:
    return decision("decline", 0)


def as_the_handlers(claim_id: str) -> AIMessage:
    expected = answer_key()[claim_id]
    return decision(expected["decision"], expected["payout"])


class ClaimAgents(StubModel):
    """Claim agents' model for a round's evaluations: each copy decided by
    `decides`, given the claim it copies, and the copies it was asked about."""

    decides: Callable[[str], AIMessage]
    asked: list[str] = Field(default_factory=list)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        first = next(m for m in messages if isinstance(m, HumanMessage))
        copy_id = str(first.content).removeprefix("Claim ")
        self.asked.append(copy_id)
        reply = costing(self.decides(copy_id.rsplit("-E", 1)[0]), CLAIM_COST)
        return ChatResult(generations=[ChatGeneration(message=reply)])


def claim_agents(decides: Callable[[str], AIMessage] = declines) -> ClaimAgents:
    return ClaimAgents(messages=iter([]), decides=decides)
