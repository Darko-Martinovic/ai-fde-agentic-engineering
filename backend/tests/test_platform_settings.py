import pytest

from backend.tests.sign_ins import DANA, MARCUS, headers
from backend.tests.workflow_steps import approved, pay

FIRST = {
    "approval_limit": 1000.0,
    "objectives": {"accuracy": 0.6, "grade": 1.0},
    "noise": {
        "accuracy": 0.1,
        "grade": 0.15,
        "cost_per_claim": 0.15,
        "seconds_per_claim": 0.15,
    },
    "tolerance": {
        "accuracy": 0.1,
        "grade": 0.15,
        "cost_per_claim": 1.0,
        "seconds_per_claim": 0.25,
    },
    "spending_limit": 0.5,
    "agents": 25,
}
VALUES = tuple(FIRST)


def change(client, handler=DANA, **changes):
    return client.put("/api/settings", json=FIRST | changes, headers=headers(handler))


def test_seeding_makes_the_first_settings_from_the_data_files(client):
    view = client.get("/api/settings").json()
    settings = view["settings"]
    assert {name: settings[name] for name in VALUES} == FIRST
    assert (settings["number"], settings["changed_by"]) == (1, None)
    luna = view["models_allowed"][0]
    assert (luna["input_price"], luna["output_price"]) == (0.1, 0.5)


def test_a_senior_handler_changes_the_settings_and_the_old_are_kept(client):
    changed = change(client, spending_limit=0.75)
    assert changed.status_code == 200
    settings = changed.json()["settings"]
    assert (settings["number"], settings["changed_by"], settings["spending_limit"]) == (
        2,
        "HND-01",
        0.75,
    )
    assert settings["changed_at"]


def test_a_handler_who_cant_sign_off_over_the_limit_cant_change_them(client):
    refused = change(client, handler=MARCUS, spending_limit=0.75)
    assert (refused.status_code, refused.json()["detail"]) == (
        403,
        "Only a handler who can sign off payouts over $1,000.00 can change the"
        " settings. Marcus Oyelaran can't.",
    )
    assert client.get("/api/settings").json()["settings"]["number"] == 1


def test_changing_them_needs_a_sign_in(client):
    assert client.put("/api/settings", json=FIRST).status_code == 401


@pytest.mark.parametrize(
    "bad",
    [
        {"approval_limit": 0},
        {"objectives": {"accuracy": 1.5, "grade": 1.0}},
        {"objectives": {"accuracy": 0.6, "grade": 4}},
        {"noise": FIRST["noise"] | {"grade": -0.1}},
        {"spending_limit": 0},
        {"agents": 26},
    ],
)
def test_settings_out_of_range_are_refused(client, bad):
    assert change(client, **bad).status_code == 422
    assert client.get("/api/settings").json()["settings"]["number"] == 1


def test_a_raised_limit_applies_to_the_decisions_after_it(client):
    approved(client, "CLM-1002", 1350)
    change(client, approval_limit=1500.0)
    approved(client, "CLM-1004", 1350)
    assert client.get("/api/claims/CLM-1002").json()["status"] == "awaiting_sign_off"
    assert pay(client, "CLM-1002", 1350).status_code == 409
    assert client.get("/api/claims/CLM-1004").json()["status"] == "in_progress"
    assert pay(client, "CLM-1004", 1350).json()["status"] == "decided"


def test_a_lowered_limit_holds_the_next_payout(client):
    change(client, approval_limit=500.0)
    claim = approved(client, "CLM-1004", 600).json()
    assert claim["status"] == "awaiting_sign_off"
    assert pay(client, "CLM-1004", 600).status_code == 409
