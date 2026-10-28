"""Rounds of improvement as the agent's service records them: proposals that
change nothing until a handler approves them, the version under test, the
verdict, stopping, and where a round has got to."""

import httpx
import pytest

from backend import agent_service
from backend.tests.round_steps import (
    CHANGE,
    DANA_ID,
    MARCUS_ID,
    a_round,
    approved_change,
    create_round,
    evaluate,
    finish,
    first_evaluations,
    propose,
    propose_recipe,
    review,
    settings_with,
    stop,
    tried,
)
from backend.tests.sign_ins import DANA, MARCUS, headers


@pytest.fixture
def asked(monkeypatch):
    """Stand in for the agent's service: what it was asked to do."""
    calls = []

    def service(url, json=None, timeout=None):
        calls.append((url, json))
        return httpx.Response(202, json={"round_id": 1, "proposal_id": 1})

    monkeypatch.setattr(agent_service.httpx, "post", service)
    return calls


def configuration(client):
    return client.get("/api/configuration").json()


def test_a_round_starts_from_the_current_settings_recipe_and_version(client):
    started = create_round(client).json()
    assert started["round_id"] == 1
    assert started["status"] == "open"
    assert started["started_by"] == DANA_ID
    assert (started["settings_number"], started["recipe_number"]) == (1, 1)
    assert started["version_before"] == 1
    assert started["first_evaluations"] == ["evaluation", "held_out", "held_out"]
    assert started["improver_model"] == "openai/gpt-6-luna"
    assert started["improver"]["options"]["reasoning_effort"] == "medium"
    assert "# Your recipe" in started["instructions"]
    assert "Call read_results" in started["instructions"]
    assert started["stage"] == "first_evaluations"
    assert started["progress"] == {"step": 1, "of": 3}


def test_only_a_senior_handler_starts_a_round(client):
    refused = create_round(client, handler_id=MARCUS_ID)
    assert refused.status_code == 403
    assert "start a round of improvement" in refused.json()["detail"]


def test_a_round_refuses_while_one_is_open(client):
    a_round(client)
    refused = create_round(client)
    assert refused.status_code == 409
    assert refused.json()["detail"] == "Round 1 is still open"


def test_a_proposal_changes_nothing_until_a_handler_approves_it(client):
    round_id = a_round(client)
    first_evaluations(client, round_id)
    proposal = propose(client, round_id).json()
    assert proposal["review"] is None
    assert [v["number"] for v in configuration(client)["versions"]] == [1]
    assert client.post(f"/api/rounds/{round_id}/versions").status_code == 409
    review(client, round_id, proposal["proposal_id"])
    made = client.post(f"/api/rounds/{round_id}/versions").json()
    assert made["version_tried"] == 2
    versions = configuration(client)
    assert versions["current"] == 1
    newest = versions["versions"][0]
    assert (newest["number"], newest["status"]) == (2, "under_test")
    assert (newest["proposed_by"], newest["approved_by"]) == ("Round 1", DANA_ID)
    again = client.post(f"/api/rounds/{round_id}/versions").json()
    assert again["version_tried"] == 2
    assert [v["number"] for v in configuration(client)["versions"]] == [2, 1]


def test_a_change_to_a_model_not_allowed_is_refused(client):
    round_id = a_round(client)
    refused = propose(client, round_id, CHANGE | {"model": "openai/gpt-7"})
    assert refused.status_code == 422
    assert "isn't allowed" in refused.json()["detail"]
    effort = propose(client, round_id, CHANGE | {"reasoning_effort": "high"})
    assert effort.status_code == 422


def test_only_a_senior_handler_reviews_a_proposal(client):
    round_id = a_round(client)
    proposal_id = propose(client, round_id).json()["proposal_id"]
    refused = review(client, round_id, proposal_id, handler_id=MARCUS_ID)
    assert refused.status_code == 403
    assert "Marcus Oyelaran can't" in refused.json()["detail"]
    assert client.get(f"/api/rounds/{round_id}").json()["waiting"]["review"] is None


def test_one_proposal_waits_at_a_time(client):
    round_id = a_round(client)
    proposal_id = propose(client, round_id).json()["proposal_id"]
    assert propose(client, round_id).status_code == 409
    assert propose_recipe(client, round_id).status_code == 409
    review(client, round_id, proposal_id, approved=False, note="Too vague.")
    rejected = client.get("/api/improvement").json()["rounds"][0]
    assert rejected["waiting"] is None
    assert propose(client, round_id).status_code == 200


def test_a_review_of_a_proposal_not_waiting_asks_nothing_of_the_service(client, asked):
    first = a_round(client)
    old = propose(client, first).json()["proposal_id"]
    finish(client, first)
    second = a_round(client)
    waiting = propose(client, second).json()["proposal_id"]
    review(client, second, waiting, approved=False, note="No.")
    approval = "/api/improvement/rounds/{}/proposals/{}/approval"
    other = client.post(approval.format(second, old), headers=headers(DANA))
    assert other.status_code == 404
    done = client.post(approval.format(second, waiting), headers=headers(DANA))
    assert done.status_code == 409
    assert done.json()["detail"] == f"Proposal {waiting} isn't waiting for a review"
    assert asked == []


def test_an_approval_on_the_dashboard_goes_to_the_service(client, asked):
    round_id = a_round(client)
    proposal_id = propose(client, round_id).json()["proposal_id"]
    path = f"/api/improvement/rounds/{round_id}/proposals/{proposal_id}"
    approved = client.post(f"{path}/approval", headers=headers(DANA))
    assert approved.status_code == 202
    rejected = client.post(
        f"{path}/rejection", json={"note": "Too vague."}, headers=headers(DANA)
    )
    assert rejected.status_code == 202
    assert [body for _, body in asked] == [
        {"handler_id": DANA_ID, "approved": True, "note": ""},
        {"handler_id": DANA_ID, "approved": False, "note": "Too vague."},
    ]
    assert asked[0][0].endswith(
        f"/api/rounds/{round_id}/proposals/{proposal_id}/review"
    )


@pytest.mark.parametrize(
    ("path", "body", "action"),
    [
        ("/api/improvement/rounds", None, "start a round of improvement"),
        ("/api/improvement/rounds/1/stop", None, "stop a round of improvement"),
        (
            "/api/improvement/rounds/1/proposals/1/approval",
            None,
            "review the improver's proposals",
        ),
        (
            "/api/improvement/rounds/1/proposals/1/rejection",
            {"note": "No."},
            "review the improver's proposals",
        ),
    ],
)
def test_a_handler_who_cant_sign_off_over_the_limit_cant_steer_rounds(
    client, asked, path, body, action
):
    round_id = a_round(client)
    propose(client, round_id)
    assert client.post(path, json=body).status_code == 401
    refused = client.post(path, json=body, headers=headers(MARCUS))
    assert refused.status_code == 403
    assert refused.json()["detail"] == (
        f"Only a handler who can sign off payouts over $1,000.00 can {action}."
        " Marcus Oyelaran can't."
    )
    assert asked == []
    assert client.get(f"/api/rounds/{round_id}").json()["status"] == "open"


def test_a_start_on_the_dashboard_is_refused_while_a_round_is_open(client, asked):
    started = client.post("/api/improvement/rounds", headers=headers(DANA))
    assert started.status_code == 202
    assert asked[0][1] == {"handler_id": DANA_ID}
    a_round(client)
    refused = client.post("/api/improvement/rounds", headers=headers(DANA))
    assert refused.status_code == 409
    assert len(asked) == 1


def test_a_round_keeps_its_settings_row_after_a_change(client):
    round_id = a_round(client)
    settings_with(client, spending_limit=2.0)
    kept = client.get(f"/api/rounds/{round_id}").json()
    assert (kept["settings_number"], kept["spending_limit"]) == (1, 0.5)


def test_stopping_a_round_rolls_back_its_version_under_test(client):
    round_id = a_round(client)
    first_evaluations(client, round_id)
    approved_change(client, round_id)
    stopped = stop(client, round_id).json()
    assert stopped["status"] == "stopped"
    assert stopped["stopped_by"] == DANA_ID
    assert stopped["stop_reason"] == "Stopped by Dana Whitfield"
    versions = configuration(client)
    assert versions["current"] == 1
    assert versions["versions"][0]["status"] == "rolled_back"
    for refused in (
        propose(client, round_id),
        client.post(f"/api/rounds/{round_id}/verdict"),
        evaluate(client, round_id, "evaluation"),
        finish(client, round_id),
    ):
        assert refused.status_code == 409
        assert refused.json()["detail"] == f"Round {round_id} is stopped"


# Objectives a few right decisions meet, so the tests decide few claims
LOW_OBJECTIVES = {"accuracy": 0.1, "grade": 0.1}


def test_a_round_stopped_after_its_verdict_keeps_the_version(client):
    settings_with(client, objectives=LOW_OBJECTIVES)
    round_id = a_round(client)
    first_evaluations(client, round_id, right=0.2)
    approved_change(client, round_id)
    verdict = tried(client, round_id, right=0.4).json()
    assert verdict["kept"], verdict["why"]
    assert verdict["why"] == "accuracy, grade improved"
    assert verdict["current_version"] == 2
    stop(client, round_id)
    assert configuration(client)["current"] == 2


def test_a_version_no_better_is_rolled_back_with_why(client):
    settings_with(client, objectives=LOW_OBJECTIVES)
    round_id = a_round(client)
    first_evaluations(client, round_id, right=0.2)
    approved_change(client, round_id)
    verdict = tried(client, round_id, right=0.2).json()
    assert (verdict["kept"], verdict["why"]) == (
        False,
        "no score improved by more than the noise",
    )
    assert (
        verdict["held_out_before"]["accuracy"] == verdict["held_out_after"]["accuracy"]
    )
    assert client.post(f"/api/rounds/{round_id}/verdict").json() == verdict
    assert configuration(client)["current"] == 1


def test_a_round_with_no_proposal_finishes_with_none_tried(client):
    round_id = a_round(client)
    first_evaluations(client, round_id)
    finished = finish(client, round_id).json()
    assert (finished["status"], finished["version_tried"]) == ("finished", None)


def test_a_version_never_evaluated_is_rolled_back_when_the_round_ends(client):
    round_id = a_round(client)
    first_evaluations(client, round_id)
    approved_change(client, round_id)
    finish(client, round_id)
    newest = configuration(client)["versions"][0]
    assert newest["status"] == "rolled_back"
    assert newest["verdict_reason"] == "the round ended before it was evaluated"


def test_an_approved_recipe_becomes_the_current_one(client):
    round_id = a_round(client)
    proposal_id = propose_recipe(client, round_id).json()["proposal_id"]
    review(client, round_id, proposal_id)
    made = client.post(f"/api/rounds/{round_id}/recipes").json()
    assert (made["number"], made["based_on"]) == (2, 1)
    assert client.post(f"/api/rounds/{round_id}/recipes").json() == made
    improvement = client.get("/api/improvement").json()
    assert improvement["current_recipe"] == 2
    details = client.get("/api/improvement/recipes/2").json()
    assert any(
        line["kind"] == "added" for hunk in details["changes"] for line in hunk["lines"]
    )
    assert client.get("/api/improvement/recipes/9").status_code == 404


def stage(client, round_id):
    worked = client.get(f"/api/rounds/{round_id}").json()
    progress = worked["progress"]
    return worked["stage"], (progress["step"], progress["of"]) if progress else None


def test_a_round_shows_each_stage_as_it_reaches_it(client):
    round_id = a_round(client)
    assert stage(client, round_id) == ("first_evaluations", (1, 3))
    evaluate(client, round_id, "evaluation")
    assert stage(client, round_id) == ("first_evaluations", (2, 3))
    evaluate(client, round_id, "held_out")
    evaluate(client, round_id, "held_out")
    assert stage(client, round_id) == ("improving", None)
    proposal_id = propose(client, round_id).json()["proposal_id"]
    assert stage(client, round_id) == ("change_waiting", None)
    review(client, round_id, proposal_id)
    client.post(f"/api/rounds/{round_id}/versions")
    assert stage(client, round_id) == ("evaluating", (1, 3))
    evaluate(client, round_id, "evaluation")
    evaluate(client, round_id, "held_out")
    assert stage(client, round_id) == ("evaluating", (3, 3))
    evaluate(client, round_id, "held_out")
    assert stage(client, round_id) == ("verdict", None)
    client.post(f"/api/rounds/{round_id}/verdict")
    assert stage(client, round_id) == ("verdict", None)
    propose_recipe(client, round_id)
    assert stage(client, round_id) == ("recipe_waiting", None)
    stop(client, round_id)
    assert stage(client, round_id) == ("stopped", None)
    finished = a_round(client)
    finish(client, finished)
    assert client.get("/api/improvement").json()["rounds"][0]["stage"] == "finished"


def test_a_restart_stops_the_open_rounds_not_waiting_for_a_handler(client):
    working = a_round(client)
    finish(client, working)
    waiting = a_round(client)
    propose(client, waiting)
    assert client.post("/api/rounds/stop-all").json() == {"round_ids": []}
    review(client, waiting, 1, approved=False, note="No.")
    assert client.post("/api/rounds/stop-all").json() == {"round_ids": [waiting]}
    assert client.get(f"/api/rounds/{waiting}").json()["stop_reason"] == (
        "The agent's service restarted while the round was working"
    )


def test_a_round_shows_each_proposal_beside_what_it_would_change(client):
    round_id = a_round(client)
    propose(client, round_id, CHANGE | {"reasoning_effort": "medium"})
    waiting = client.get(f"/api/rounds/{round_id}").json()["waiting"]
    assert (waiting["model_before"], waiting["reasoning_effort_before"]) == (
        "openai/gpt-6-luna",
        "low",
    )
    lines = [line for hunk in waiting["changes"] for line in hunk["lines"]]
    assert {"kind": "added", "text": "Decide the claim with care."} in lines
    review(client, round_id, waiting["proposal_id"], approved=False, note="No.")
    propose_recipe(client, round_id)
    worked = client.get("/api/improvement").json()["rounds"][0]
    assert [p["kind"] for p in worked["proposals"]] == ["change", "recipe"]
    recipe = worked["waiting"]
    assert recipe["model_before"] is None
    assert any(
        line["kind"] == "removed"
        for hunk in recipe["changes"]
        for line in hunk["lines"]
    )
