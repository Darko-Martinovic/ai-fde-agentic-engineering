"""Every tool the agent uses, and the context its tools read."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

from agent import api
from agent.claims import waiting_claims


@dataclass(frozen=True)
class ClaimContext:
    """What a claim agent's tools know: the run it works in, or None outside a
    run, the claim it works on and the claim's thread."""

    run_id: int | None
    claim_id: str
    thread_id: str


@dataclass(frozen=True)
class RunContext:
    """What the queue agent's tools know: its run, the run's cap, and how to hand
    a claim to a claim agent and get its one-line report back."""

    run_id: int
    cap: int
    work: Callable[[str], str]


Benefit = Literal[
    "trip_cancellation",
    "trip_interruption",
    "trip_delay",
    "baggage_delay",
    "baggage",
    "passport",
    "emergency_medical",
]


class Line(BaseModel):
    """One covered item or expense on a claim."""

    description: str = Field(description="What the item or expense is")
    amount: float = Field(
        description="The total claimed for the line in US dollars, before any"
        " limits. For several items, the total for all of them"
    )
    quantity: int = Field(
        default=1,
        ge=1,
        description="How many separate items the line holds, such as 3 for three"
        " shirts. A pair or a set is one item",
    )
    kind: Literal[
        "item", "electronics", "cash", "expense", "hotel", "meals_without_receipts"
    ] = Field(
        description="item: a belonging, or a pair or set that counts as one item."
        " electronics: only a phone, tablet, laptop, camera or its lens, e-reader"
        " or smartwatch; any other device is an item. cash: cash that was lost or"
        " stolen. expense: any other cost with a receipt, such as a medical bill, a"
        " meal, a taxi, a fee or a prepaid trip cost. hotel: a hotel during a trip"
        " delay. meals_without_receipts: meals during a trip delay with no receipts."
    )
    nights: int = Field(ge=0, description="For a hotel, the nights; otherwise 0")
    hours: float = Field(
        ge=0,
        description="For meals without receipts, the delay in hours; otherwise 0",
    )


class Todo(BaseModel):
    content: str = Field(description="What to do, such as 'Work CLM-1001'")
    status: Literal["pending", "in_progress", "completed", "left_for_handler"]


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
def calculate_payout(
    benefit: Benefit,
    lines: list[Line],
    paid_by_others: float,
    runtime: ToolRuntime[ClaimContext],
) -> dict[str, Any]:
    """Work out the payout on the claim if you approve it, with UnderCover's payout
    rules: the covered lines, with any excluded ones left out, the benefit they're
    paid under, and anything a carrier, hotel or other party has paid or refunded
    for the same loss (0 if nothing). Returns the calculation step by step, the
    payout and whether it needs a handler's sign-off."""
    return api.calculate_payout(
        runtime.context.claim_id,
        {
            "benefit": benefit,
            "lines": [line.model_dump() for line in lines],
            "paid_by_others": paid_by_others,
        },
    )


@tool
def decide_claim(
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    reasons: str,
    policy_section: str,
    runtime: ToolRuntime[ClaimContext],
) -> Command[Any]:
    """Record your decision on the claim: the payout, two or three sentences of
    reasons and the section of the policy wording it rests on. It's the last
    thing you do on the claim."""
    claim = api.decide_claim(
        runtime.context.claim_id,
        {
            "decision": decision,
            "payout": payout,
            "reasons": reasons,
            "policy_section": policy_section,
        },
    )
    recorded = ToolMessage(
        json.dumps(claim, ensure_ascii=False),
        name=decide_claim.name,
        tool_call_id=runtime.tool_call_id,
    )
    return Command(
        update={
            "messages": [recorded],
            "decision": decision,
            "status": claim["status"],
        }
    )


CLAIM_TOOLS = [
    get_claim,
    get_policy,
    get_customer,
    search_documents,
    read_section,
    calculate_payout,
    decide_claim,
]


@tool
def list_waiting_claims() -> list[dict[str, Any]]:
    """List the claims waiting in the queue, with each one's type, amount claimed
    and the date it was submitted."""
    return [
        {
            key: claim[key]
            for key in ("claim_id", "claim_type", "amount_claimed", "submitted_on")
        }
        for claim in waiting_claims()
    ]


@tool
def write_todos(todos: list[Todo], runtime: ToolRuntime[RunContext]) -> str:
    """Write your to-do list for this run, replacing the one before. The claims
    team watches it on the dashboard."""
    api.write_todos(runtime.context.run_id, [todo.model_dump() for todo in todos])
    return f"Your to-do list has {len(todos)} items."


@tool
def work_claim(claim_id: str, runtime: ToolRuntime[RunContext]) -> str:
    """Hand one waiting claim to a claim agent, which works it from a clean start
    and reports back in a line: the decision and payout, with the reasons for a
    decline or a referral, or what went wrong."""
    return runtime.context.work(claim_id)


QUEUE_TOOLS = [list_waiting_claims, write_todos, work_claim]
