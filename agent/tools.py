"""Every tool the agent uses, and the context its tools read."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from langchain.tools import ToolRuntime, tool
from pydantic import BaseModel, Field

from agent import api


@dataclass(frozen=True)
class RunScope:
    """What every agent in a run knows: the run."""

    run_id: int


@dataclass(frozen=True)
class ClaimContext(RunScope):
    """What a claim agent's tools know: its run, the claim it works on and the
    claim's thread."""

    claim_id: str
    thread_id: str


@dataclass(frozen=True)
class RunContext(RunScope):
    """What the queue agent's tools know: its run, the run's cap, and how to hand
    a claim to a claim agent and get its one-line report back."""

    cap: int
    work: Callable[[str], str]


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


def waiting_claims() -> list[dict[str, Any]]:
    """Return the claims waiting in the queue, in claim id order."""
    return [claim for claim in api.list_claims() if claim["status"] == "waiting"]


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
    and reports back in a line: the decision and payout, or what went wrong."""
    return runtime.context.work(claim_id)


QUEUE_TOOLS = [list_waiting_claims, write_todos, work_claim]
