"""The agent's key, and who may call each route: the agent's side with its key,
a signed-in handler, either, or anyone."""

import re

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import agent_service
from backend.agent_key import KEY_HEADER, NEEDS_THE_KEY
from backend.main import app
from backend.tests.sign_ins import DANA, agent_headers, headers

AGENT_ONLY = "the agent's key"
EITHER = "the key or a sign-in"
SIGNED_IN = "a sign-in"
OPEN = "nothing"

GUARDS = {
    "health": OPEN,
    **dict.fromkeys(
        [
            "start_claim",
            "fail_claim",
            "record_step",
            "decide_claim",
            "pay_claim",
            "calculate_payout",
            "record_model_call",
            "record_work_time",
            "list_sections",
            "search_documents",
            "get_version",
            "get_current_version",
            "get_screening_model",
            "create_dispatch",
            "create_evaluation",
            "create_round_evaluation",
            "record_run_claims",
            "finish_run",
            "stop_runs",
            "create_round",
            "stop_rounds",
            "get_round",
            "get_improver_view",
            "record_change_proposal",
            "record_recipe_proposal",
            "record_review",
            "create_version",
            "create_recipe",
            "record_verdict",
            "record_improver_call",
            "finish_round",
        ],
        AGENT_ONLY,
    ),
    **dict.fromkeys(
        ["list_claims", "get_claim", "get_policy", "get_customer", "read_section"],
        EITHER,
    ),
    **dict.fromkeys(
        [
            "list_steps",
            "list_handlers",
            "get_signed_in_handler",
            "get_policy_wording",
            "get_latest_dispatch",
            "get_insights",
            "get_configuration",
            "get_version_details",
            "get_settings",
            "list_evaluations",
            "get_evaluation",
            "get_improvement",
            "get_recipe",
            "review_payout",
            "decide_as_handler",
            "start_dispatch",
            "stop_run",
            "start_evaluation",
            "change_settings",
            "start_round",
            "stop_round",
            "approve_proposal",
            "reject_proposal",
        ],
        SIGNED_IN,
    ),
}

# A value for each kind of path parameter, so every route can be called
SAMPLES = {
    "claim_id": "CLM-1001",
    "policy_id": "POL-2001",
    "customer_id": "CUS-3001",
    "document": "wording",
}
PARAMETER = re.compile(r"\{(\w+)\}")

# Every operation in the app's API document, with its path and method
OPERATIONS = [
    (operation["operationId"], path, method.upper())
    for path, methods in app.openapi()["paths"].items()
    for method, operation in methods.items()
]


@pytest.fixture(autouse=True)
def no_service(monkeypatch):
    """The agent's service can't be reached, so no route here starts anything."""

    def unreachable(path, body):
        raise HTTPException(503, "The test reaches no agent's service")

    monkeypatch.setattr(agent_service, "ask", unreachable)


def called(path: str, method: str, sent: dict[str, str]) -> int:
    """The status a route answers with these headers, its body left empty."""
    filled = PARAMETER.sub(lambda found: SAMPLES.get(found[1], "1"), path)
    response = TestClient(app, headers=sent).request(method, filled, json={})
    return response.status_code


def test_every_route_has_a_guard_in_the_table():
    assert sorted(operation for operation, _, _ in OPERATIONS) == sorted(GUARDS)


@pytest.mark.parametrize(
    ("operation", "path", "method"), OPERATIONS, ids=[op for op, _, _ in OPERATIONS]
)
def test_each_route_lets_through_only_who_may_call_it(operation, path, method):
    guard = GUARDS[operation]
    let_through = {
        "nobody": guard == OPEN,
        "the agent": guard in (OPEN, AGENT_ONLY, EITHER),
        "a handler": guard in (OPEN, EITHER, SIGNED_IN),
    }
    statuses = {
        "nobody": called(path, method, {}),
        "the agent": called(path, method, agent_headers()),
        "a handler": called(path, method, headers(DANA)),
    }
    assert {who: status != 401 for who, status in statuses.items()} == let_through


def test_an_agent_route_needs_the_right_key():
    path = "/api/versions/current"
    assert TestClient(app).get(path).status_code == 401
    wrong = TestClient(app, headers={KEY_HEADER: "not-the-key"}).get(path)
    assert (wrong.status_code, wrong.json()["detail"]) == (401, NEEDS_THE_KEY)
    assert TestClient(app, headers=agent_headers()).get(path).status_code == 200


def test_a_shared_read_takes_the_key_or_a_sign_in():
    path = "/api/claims/CLM-1001"
    assert TestClient(app, headers=agent_headers()).get(path).status_code == 200
    assert TestClient(app, headers=headers(DANA)).get(path).status_code == 200
    refused = TestClient(app).get(path)
    assert (refused.status_code, refused.json()["detail"]) == (
        401,
        "Sign in as a handler first",
    )


def test_the_key_never_stands_in_for_a_handler():
    agent = TestClient(app, headers=agent_headers())
    assert agent.get("/api/me").status_code == 401
    assert agent.get("/api/insights").status_code == 401


def test_with_no_key_set_handlers_carry_on_and_every_key_is_refused(monkeypatch):
    monkeypatch.delenv("UNDERCOVER_API_KEY")
    with TestClient(app) as started:
        assert started.get("/api/health").status_code == 200
        assert started.get("/api/claims", headers=headers(DANA)).status_code == 200
        agent = agent_headers()
        assert started.get("/api/versions/current", headers=agent).status_code == 401
        assert started.get("/api/claims", headers=agent).status_code == 401
