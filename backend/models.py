"""The shapes of UnderCover's records in the API."""

from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

ClaimStatus = Literal[
    "waiting",
    "in_progress",
    "awaiting_sign_off",
    "referred",
    "left_for_handler",
    "decided",
]
# The states a handler decides a claim from: the agent referred it, or it failed
# twice and was left for a handler
FOR_A_HANDLER: tuple[ClaimStatus, ...] = ("referred", "left_for_handler")
StepKind = Literal["tool_call", "tool_result", "reply", "section", "failure"]
DecisionKind = Literal["approve", "decline", "refer"]


DocumentName = Literal["wording", "manual"]
# The agents with instructions of their own
AgentName = Literal["queue", "claim"]


class SectionTitle(BaseModel):
    document: DocumentName
    document_title: str
    number: int
    title: str


class Section(SectionTitle):
    text: str


class StepIn(BaseModel):
    thread_id: str = Field(min_length=1)
    kind: StepKind
    text: str

    @model_validator(mode="after")
    def section_names_a_section(self) -> Self:
        """A section step's text is the section read, so the dashboard can show it."""
        if self.kind == "section":
            SectionTitle.model_validate_json(self.text)
        return self


class Step(StepIn):
    recorded_at: datetime


def check_payout(decision: str, payout: float) -> None:
    """An approval pays something, and a decline or a referral pays nothing."""
    if (decision == "approve") != (payout > 0):
        raise ValueError(
            "An approval pays more than $0.00, and a decline or a referral pays $0.00"
        )


class DecisionIn(BaseModel):
    decision: DecisionKind
    payout: float = Field(ge=0)
    reasons: str = Field(min_length=1)
    policy_section: str = Field(min_length=1)

    @model_validator(mode="after")
    def payout_fits_decision(self) -> Self:
        check_payout(self.decision, self.payout)
        return self


class StartIn(BaseModel):
    run_id: int
    thread_id: str = Field(min_length=1)


class FailureIn(BaseModel):
    thread_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class HandlerDecisionIn(BaseModel):
    handler_id: str
    decision: Literal["approve", "decline"]
    payout: float = Field(ge=0)
    reasons: str = Field(min_length=1)

    @model_validator(mode="after")
    def payout_fits_decision(self) -> Self:
        check_payout(self.decision, self.payout)
        return self


class Decision(BaseModel):
    decided_by: str
    decision: DecisionKind
    payout: float
    reasons: str
    policy_section: str | None
    decided_at: datetime


class PaymentIn(BaseModel):
    amount: float = Field(gt=0)


class Payment(BaseModel):
    amount: float
    authorized_by: str
    paid_at: datetime


class SignOffIn(BaseModel):
    handler_id: str


class Item(BaseModel):
    description: str
    category: str
    amount: float


class Document(BaseModel):
    name: str
    type: str
    content: str


class ClaimSummary(BaseModel):
    claim_id: str
    claim_type: str
    customer_name: str
    amount_claimed: float
    submitted_on: date
    status: ClaimStatus
    decision: DecisionKind | None
    payout: float | None
    paid: float | None


class Claim(BaseModel):
    claim_id: str
    policy_id: str
    customer_id: str
    claim_type: str
    submitted_on: date
    incident_date: date
    incident_location: str
    summary: str
    story: str
    items: list[Item]
    amount_claimed: float
    documents: list[Document]
    status: ClaimStatus
    decisions: list[Decision]
    payment: Payment | None


class Plan(BaseModel):
    plan: str
    name: str
    trip_cancellation_max: float
    trip_delay_waiting_hours: int
    trip_delay_max: float
    baggage_delay_waiting_hours: int
    baggage_delay_max: float
    baggage_max: float
    per_item_limit: float
    passport_max: float
    emergency_medical_max: float
    deductible: float


class AddOn(BaseModel):
    add_on: str
    name: str
    effect: str
    electronics_per_item_limit: float | None = None


class Trip(BaseModel):
    destination: str
    departs_on: date
    returns_on: date
    trip_cost: float


class Policy(BaseModel):
    policy_id: str
    customer_id: str
    plan: Plan
    deductible_applies_to: list[str]
    add_ons: list[AddOn]
    purchased_on: date
    sold_through: str
    trip: Trip
    travelers: list[str]
    status: str


class Address(BaseModel):
    street: str
    city: str
    state: str
    zip: str


class PreviousClaim(BaseModel):
    claim_id: str
    filed_on: date
    incident_date: date
    claim_type: str
    summary: str
    outcome: str
    amount_paid: float


class Customer(BaseModel):
    customer_id: str
    name: str
    email: str
    phone: str
    date_of_birth: date
    address: Address
    customer_since: date
    previous_claims: list[PreviousClaim]


class Handler(BaseModel):
    handler_id: str
    name: str
    role: str
    email: str
    can_approve_over_limit: bool


RunStatus = Literal["running", "finished", "stopped"]
TodoStatus = Literal["pending", "in_progress", "completed", "left_for_handler"]


class Todo(BaseModel):
    content: str = Field(min_length=1)
    status: TodoStatus


class RunIn(BaseModel):
    mode: Literal["queue", "claim"]
    cap: int = Field(ge=1)
    model: str = Field(min_length=1)


class Usage(BaseModel):
    model_calls: int
    input_tokens: int
    output_tokens: int
    cost: float
    seconds: float


class Run(RunIn):
    run_id: int
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None
    summary: str | None
    todos: list[Todo]
    claims_started: list[str]
    usage: Usage


class TodosIn(BaseModel):
    todos: list[Todo]


class FinishIn(BaseModel):
    summary: str


class UsageIn(BaseModel):
    claim_id: str | None
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost: float = Field(ge=0)
    seconds: float = Field(ge=0)
