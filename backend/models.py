"""The shapes of UnderCover's records in the API."""

from datetime import date
from typing import Literal

from pydantic import BaseModel

ClaimStatus = Literal[
    "waiting", "in_progress", "awaiting_sign_off", "referred", "decided"
]


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
