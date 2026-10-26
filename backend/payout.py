"""UnderCover's payout rules for an approved claim: section 10 of the policy
wording, the plan's limits, and sections 7 and 10 of the claims manual."""

from dataclasses import dataclass, field
from math import ceil, inf
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from backend.models import Policy

# Cash is paid up to this much in all (policy wording 5). A hotel during a trip
# delay is paid up to this much a night for each room, one room for every two
# travelers (claims manual 7). Meals without receipts are paid for each day or
# part of a day of the delay (claims manual 10).
CASH_LIMIT = 100.0
HOTEL_NIGHT_LIMIT = 350.0
TRAVELERS_A_ROOM = 2
HOURS_A_DAY = 24

Benefit = Literal[
    "trip_cancellation",
    "trip_interruption",
    "trip_delay",
    "baggage_delay",
    "baggage",
    "passport",
    "emergency_medical",
]
LineKind = Literal[
    "item", "electronics", "cash", "expense", "hotel", "meals_without_receipts"
]
# The plan's maximum for each benefit. Trip Interruption shares Cancellation's.
MAXIMUM: dict[Benefit, str] = {
    "trip_cancellation": "trip_cancellation_max",
    "trip_interruption": "trip_cancellation_max",
    "trip_delay": "trip_delay_max",
    "baggage_delay": "baggage_delay_max",
    "baggage": "baggage_max",
    "passport": "passport_max",
    "emergency_medical": "emergency_medical_max",
}
CAPPED_AT_TRIP_COST: tuple[Benefit, ...] = ("trip_cancellation", "trip_interruption")


class Line(BaseModel):
    description: str = Field(min_length=1)
    amount: float = Field(ge=0)
    quantity: int = Field(ge=1)
    kind: LineKind
    nights: int = Field(ge=0)
    hours: float = Field(ge=0)

    @model_validator(mode="after")
    def counts_what_its_limit_needs(self) -> Self:
        """A hotel's limit is by the night and meals without receipts by the day,
        so a line of either without them would be limited to nothing."""
        if self.kind == "hotel" and self.nights < 1:
            raise ValueError("A hotel line needs its nights")
        if self.kind == "meals_without_receipts" and self.hours <= 0:
            raise ValueError("A line of meals without receipts needs the delay's hours")
        return self


class PayoutIn(BaseModel):
    benefit: Benefit
    lines: list[Line]
    paid_by_others: float = Field(ge=0)


class CalculationStep(BaseModel):
    step: str
    amount: float


class Payout(BaseModel):
    calculation: list[CalculationStep]
    payout: float
    needs_sign_off: bool


@dataclass
class Calculation:
    """The calculation so far, a step at a time, each rounded to the cent."""

    steps: list[CalculationStep] = field(default_factory=list)

    def add(self, description: str, amount: float) -> None:
        self.steps.append(CalculationStep(step=description, amount=round(amount, 2)))

    @property
    def total(self) -> float:
        return sum(step.amount for step in self.steps)


def electronics_limit(policy: Policy) -> float:
    """The per-item limit for electronics: an add-on's, such as Electronics
    Plus, or the plan's."""
    raised = [a.electronics_per_item_limit for a in policy.add_ons]
    return next((limit for limit in raised if limit), policy.plan.per_item_limit)


def limit_for(line: Line, policy: Policy, meal_allowance: float) -> float:
    """The most UnderCover pays for one line, or infinity for no limit of its own."""
    travelers = len(policy.travelers)
    match line.kind:
        case "item":
            return policy.plan.per_item_limit * line.quantity
        case "electronics":
            return electronics_limit(policy) * line.quantity
        case "hotel":
            rooms = ceil(travelers / TRAVELERS_A_ROOM)
            return HOTEL_NIGHT_LIMIT * rooms * line.nights
        case "meals_without_receipts":
            return meal_allowance * travelers * ceil(line.hours / HOURS_A_DAY)
        case _:
            return inf


def covered(request: PayoutIn, policy: Policy, meal_allowance: float) -> Calculation:
    """The eligible amount of each line, the amount claimed or its limit if that
    is lower, with the claim's cash taken together."""
    calculation = Calculation()
    for line in request.lines:
        if line.kind == "cash":
            continue
        limit = limit_for(line, policy, meal_allowance)
        if line.amount > limit:
            calculation.add(f"{line.description}, limited to ${limit:,.2f}", limit)
        else:
            calculation.add(line.description, line.amount)
    cash = sum(line.amount for line in request.lines if line.kind == "cash")
    if cash:
        calculation.add(f"Cash, up to ${CASH_LIMIT:,.0f} in all", min(cash, CASH_LIMIT))
    return calculation


def benefit_maximum(policy: Policy, benefit: Benefit) -> float:
    """The most the plan pays for a benefit, and for Trip Cancellation and
    Interruption no more than the trip cost."""
    maximum = getattr(policy.plan, MAXIMUM[benefit])
    if benefit in CAPPED_AT_TRIP_COST:
        return min(maximum, policy.trip.trip_cost)
    return maximum


def work_out_payout(
    policy: Policy, request: PayoutIn, meal_allowance: float, approval_limit: float
) -> Payout:
    """Work out the payout on an approved claim, step by step, in the order
    section 10 of the wording takes it: the eligible lines, less what others have
    paid, less the deductible where it applies, no more than the benefit's
    maximum and never below zero. Over the approval limit it needs a sign-off."""
    calculation = covered(request, policy, meal_allowance)
    if request.paid_by_others:
        calculation.add(
            "Less what others have paid or refunded", -request.paid_by_others
        )
    deductible = min(policy.plan.deductible, max(calculation.total, 0))
    if request.benefit in policy.deductible_applies_to and deductible:
        calculation.add("Less the deductible", -deductible)
    maximum = benefit_maximum(policy, request.benefit)
    if calculation.total > maximum:
        calculation.add(
            f"Less the amount over the maximum of ${maximum:,.0f}",
            maximum - calculation.total,
        )
    if calculation.total < 0:
        calculation.add("Nothing is left to pay", -calculation.total)
    payout = round(calculation.total, 2)
    return Payout(
        calculation=calculation.steps,
        payout=payout,
        needs_sign_off=payout > approval_limit,
    )
