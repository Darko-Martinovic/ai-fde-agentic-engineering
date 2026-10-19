"""The shapes of UnderCover's records in the API."""

from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

ClaimStatus = Literal[
    "waiting", "in_progress", "awaiting_sign_off", "referred", "decided"
]
StepKind = Literal["tool_call", "tool_result", "reply"]


class StepIn(BaseModel):
    thread_id: str = Field(min_length=1)
    kind: StepKind
    text: str


class Step(StepIn):
    recorded_at: datetime


def check_payout(decision: str, payout: float) -> None:
    """An approval pays something, and a decline or a referral pays nothing."""
    if (decision == "approve") != (payout > 0):
        raise ValueError(
            "An approval pays more than $0.00, and a decline or a referral pays $0.00"
        )


class DecisionIn(BaseModel):
    decision: Literal["approve", "decline", "refer"]
    payout: float = Field(ge=0)
    reasons: str = Field(min_length=1)
    policy_section: str = Field(min_length=1)

    @model_validator(mode="after")
    def payout_fits_decision(self) -> Self:
        check_payout(self.decision, self.payout)
        return self


class ResolutionIn(BaseModel):
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
    decision: Literal["approve", "decline", "refer"]
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
