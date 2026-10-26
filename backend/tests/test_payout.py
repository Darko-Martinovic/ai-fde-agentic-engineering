import pytest

from backend.models import Policy
from backend.payout import Line, PayoutIn, work_out_payout

MEAL_ALLOWANCE = 35.0
APPROVAL_LIMIT = 1000.0


def line(description, amount, kind="item", **counts):
    """One line of a payout request: one item, with no nights or hours unless
    `counts` gives them."""
    return {
        "description": description,
        "amount": amount,
        "kind": kind,
        "quantity": 1,
        "nights": 0,
        "hours": 0,
    } | counts


def payout_on(client, claim_id, benefit, lines, paid_by_others=0.0):
    return client.post(
        f"/api/claims/{claim_id}/payout",
        json={"benefit": benefit, "lines": lines, "paid_by_others": paid_by_others},
    )


def policy(client, policy_id, **changes):
    """A policy as the backend gives it, with any changes for a rule's edge."""
    record = client.get(f"/api/policies/{policy_id}").json() | changes
    return Policy.model_validate(record)


def work_out(a_policy, benefit, lines, paid_by_others=0.0):
    request = PayoutIn(
        benefit=benefit,
        lines=[Line.model_validate(each) for each in lines],
        paid_by_others=paid_by_others,
    )
    return work_out_payout(a_policy, request, MEAL_ALLOWANCE, APPROVAL_LIMIT)


def test_a_trip_delay_has_no_deductible(client):
    lines = [
        line("Airport hotel", 245.0, "hotel", nights=1),
        line("Dinner and breakfast", 95.0, "expense"),
        line("Taxis", 80.0, "expense"),
    ]
    result = payout_on(client, "CLM-1001", "trip_delay", lines).json()
    assert result["payout"] == 420.0
    assert result["needs_sign_off"] is False
    assert [s["step"] for s in result["calculation"]] == [
        "Airport hotel",
        "Dinner and breakfast",
        "Taxis",
    ]


def test_emergency_medical_over_the_limit_needs_sign_off(client):
    lines = [line("Emergency room", 3800.0, "expense")]
    result = payout_on(client, "CLM-1003", "emergency_medical", lines).json()
    assert result["payout"] == 3750.0
    assert result["calculation"][-1] == {"step": "Less the deductible", "amount": -50.0}
    assert result["needs_sign_off"] is True


def test_electronics_without_the_add_on_take_the_plans_limit(client):
    lines = [line("Smartphone", 1099.0, "electronics")]
    result = payout_on(client, "CLM-1007", "baggage", lines).json()
    assert result["calculation"] == [
        {"step": "Smartphone, limited to $150.00", "amount": 150.0},
        {"step": "Less the deductible", "amount": -100.0},
    ]
    assert result["payout"] == 50.0


def test_electronics_plus_raises_the_limit(client):
    result = work_out(
        policy(client, "POL-2009"),
        "baggage",
        [line("Mirrorless camera", 1300.0, "electronics")],
    )
    assert result.calculation[0].step == "Mirrorless camera, limited to $1,200.00"
    assert result.payout == 1150.0


def test_items_by_quantity_and_what_others_paid(client):
    lines = [
        line("Suitcase", 280.0),
        line("Wool suit", 420.0),
        line("Four shirts", 120.0, quantity=4),
    ]
    result = payout_on(client, "CLM-1002", "baggage", lines, 100.0).json()
    steps = [s["step"] for s in result["calculation"]]
    assert "Wool suit, limited to $300.00" in steps
    assert "Four shirts" in steps
    assert "Less what others have paid or refunded" in steps
    assert result["payout"] == 550.0


def test_cash_is_paid_up_to_100_in_all(client):
    lines = [line("Wallet cash", 80.0, "cash"), line("Coat cash", 70.0, "cash")]
    result = work_out(policy(client, "POL-2002"), "baggage", lines)
    assert result.calculation[0].model_dump() == {
        "step": "Cash, up to $100 in all",
        "amount": 100.0,
    }
    assert result.payout == 50.0


def test_hotel_nights_are_paid_by_the_room(client):
    six_travelers = policy(client, "POL-2015")
    lines = [line("Hotel", 4000.0, "hotel", nights=2)]
    result = work_out(six_travelers, "trip_delay", lines)
    assert result.calculation[0].step == "Hotel, limited to $2,100.00"
    assert result.payout == 1500.0
    assert result.calculation[-1].step == "Less the amount over the maximum of $1,500"


def test_meals_without_receipts_per_traveler_per_day(client):
    two_travelers = policy(client, "POL-2001", travelers=["Maya Patel", "Sam Patel"])
    lines = [line("Kiosk meals", 200.0, "meals_without_receipts", hours=30)]
    result = work_out(two_travelers, "trip_delay", lines)
    assert result.calculation[0].step == "Kiosk meals, limited to $140.00"
    assert result.payout == 140.0


def test_cancellation_is_capped_at_the_trip_cost(client):
    cheap_trip = policy(client, "POL-2008")
    cheap_trip.trip.trip_cost = 1000.0
    lines = [line("Prepaid hotel", 1480.0, "expense")]
    result = work_out(cheap_trip, "trip_cancellation", lines)
    assert result.payout == 1000.0
    assert result.calculation[-1].step == "Less the amount over the maximum of $1,000"


def test_nothing_below_zero(client):
    lines = [line("Taxi", 40.0, "expense")]
    result = work_out(policy(client, "POL-2001"), "trip_delay", lines, 90.0)
    assert result.calculation[-1].model_dump() == {
        "step": "Nothing is left to pay",
        "amount": 50.0,
    }
    assert result.payout == 0.0


def test_sign_off_follows_the_stored_limit(client, approval_limit):
    approval_limit(500.0)
    lines = [line("Suitcase", 280.0), line("Wool suit", 420.0), line("Shirts", 120.0)]
    result = payout_on(client, "CLM-1002", "baggage", lines, 100.0).json()
    assert result["payout"] == 550.0
    assert result["needs_sign_off"] is True


@pytest.mark.parametrize(
    ("claim_id", "benefit", "lines", "status"),
    [
        ("CLM-1001", "trip_delay", [{"description": "Hotel", "amount": 1}], 422),
        ("CLM-1001", "trip_delay", [line("Hotel", 245.0, "hotel")], 422),
        (
            "CLM-1001",
            "trip_delay",
            [line("Meals", 70.0, "meals_without_receipts")],
            422,
        ),
        ("CLM-1001", "pets", [line("Dog", 10.0)], 422),
        ("CLM-1001", "baggage", [line("Coat", 10.0, quantity=0)], 422),
        ("CLM-9999", "baggage", [line("Coat", 10.0)], 404),
    ],
)
def test_bad_requests(client, claim_id, benefit, lines, status):
    assert payout_on(client, claim_id, benefit, lines).status_code == status


def test_working_out_records_nothing(client):
    payout_on(client, "CLM-1001", "trip_delay", [line("Taxi", 80.0, "expense")])
    claim = client.get("/api/claims/CLM-1001").json()
    assert (claim["status"], claim["decisions"]) == ("waiting", [])
