"""Every tool the agent uses, and the context its tools read."""

from dataclasses import dataclass
from typing import Any, Literal

from langchain.tools import ToolRuntime, tool

from agent import api


@dataclass(frozen=True)
class ClaimContext:
    """What a claim agent's tools know: the claim it works on and its thread."""

    claim_id: str
    thread_id: str


@tool
def get_claim(runtime: ToolRuntime[ClaimContext]) -> dict[str, Any]:
    """Get the claim you are working on in full: the story, the items claimed and
    the documents."""
    return api.get_claim(runtime.context.claim_id)


@tool
def get_policy(policy_id: str) -> dict[str, Any]:
    """Get a policy, by the claim's policy_id, with its plan's limits and add-ons."""
    return api.get_policy(policy_id)


@tool
def get_customer(customer_id: str) -> dict[str, Any]:
    """Get a customer, by the claim's customer_id, with their earlier claims."""
    return api.get_customer(customer_id)


@tool
def search_documents(query: str) -> list[dict[str, Any]]:
    """Find the sections of the policy wording and the claims manual that best
    match what you're looking for, such as "meals without receipts"."""
    return api.search_documents(query)


@tool
def read_section(document: Literal["wording", "manual"], number: int) -> dict[str, Any]:
    """Read one numbered section of the policy wording or the claims manual."""
    return api.read_section(document, number)


@tool
def decide_claim(
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    reasons: str,
    policy_section: str,
    runtime: ToolRuntime[ClaimContext],
) -> dict[str, Any]:
    """Record your decision on the claim: the payout, two or three sentences of
    reasons and the section of the policy wording it rests on."""
    return api.decide_claim(
        runtime.context.claim_id,
        {
            "decision": decision,
            "payout": payout,
            "reasons": reasons,
            "policy_section": policy_section,
        },
    )


@tool
def pay_claim(amount: float, runtime: ToolRuntime[ClaimContext]) -> dict[str, Any]:
    """Pay the approved claim its payout. Payouts over $1,000 wait for sign-off."""
    return api.pay_claim(runtime.context.claim_id, amount)


CLAIM_TOOLS = [
    get_claim,
    get_policy,
    get_customer,
    search_documents,
    read_section,
    decide_claim,
    pay_claim,
]
