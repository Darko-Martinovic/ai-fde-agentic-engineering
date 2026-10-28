"""What a round spends and may spend, a version's scores from its rounds'
evaluations, and what the improver reads of the results."""

import json

import pytest

from backend import db, spending
from backend.store import evaluations
from backend.tests.round_steps import (
    CHANGE,
    LUNA,
    a_round,
    approved_change,
    evaluate,
    finish_run,
    first_evaluations,
    settings_with,
    started,
    work,
)
from backend.version_scores import version_scores

GEMINI = "google/gemini-3.5-flash-lite"
# What the judge's B costs for each copy it grades
JUDGE_COST = 0.00002


def scores(version, evaluation_set="held_out"):
    """A version's scores on a set, which it must have."""
    with db.engine().connect() as conn:
        found = version_scores(conn, version)[evaluation_set]
    assert found is not None
    return found


def accuracy(client, finished):
    run_id = finished.json()["run_id"]
    return client.get(f"/api/evaluations/{run_id}").json()["measures"]["accuracy"]


def test_a_versions_scores_average_its_rounds_finished_whole_set_evaluations(
    client,
):
    scoreboard = {"evaluation_set": "held_out", "tiny": False, "agents": 5}
    board = client.post("/api/runs/evaluations", json=scoreboard).json()
    work(client, board, 1.0, 0)
    finish_run(client, board)
    round_id = a_round(client)
    evaluate(client, round_id, "evaluation", right=0.2)
    once = accuracy(client, evaluate(client, round_id, "held_out", right=0.2))
    twice = accuracy(client, evaluate(client, round_id, "held_out", right=0.4))
    assert scores(1).accuracy == pytest.approx((once + twice) / 2)
    assert once < twice


def test_a_stopped_evaluation_doesnt_count_in_the_scores(client):
    round_id = a_round(client)
    evaluate(client, round_id, "evaluation", right=0.2)
    once = accuracy(client, evaluate(client, round_id, "held_out", right=0.2))
    run = started(client, round_id, "held_out").json()
    work(client, run, 0.4, 0)
    finish_run(client, run, stopped=True)
    assert scores(1).accuracy == pytest.approx(once)
    assert client.get(f"/api/rounds/{round_id}").json()["status"] == "open"


def held_out_secrets():
    """The held-out claims' ids, summaries and the handlers' reasons on them."""
    with db.engine().connect() as conn:
        reasons = evaluations.handlers_reasons(conn, "held_out")
        summaries = [c["summary"] for c in evaluations.originals(conn, "held_out")]
    return list(reasons), summaries, [r["reason"] for r in reasons.values()]


def test_the_improver_sees_its_mistakes_and_only_the_scores_of_the_held_out_set(
    client,
):
    round_id = a_round(client)
    for evaluation_set in ("evaluation", "held_out", "held_out"):
        evaluate(client, round_id, evaluation_set, right=0.4)
    view = client.get(f"/api/rounds/{round_id}/view").json()
    assert view["current_version"]["number"] == 1
    assert view["current_version"]["model"] == LUNA
    assert view["scores"]["held_out"] == scores(1).model_dump()
    assert view["evaluation_set"]["wrong"]
    weakest = view["evaluation_set"]["explained_least_well"]
    assert len(weakest) == 5
    first = view["evaluation_set"]["wrong"][0]
    assert first["claim_id"].startswith("CLM-")
    assert first["summary"]
    assert first["handler"]["reason"]
    assert first["handler"]["reference"]
    assert first["agent"]["decision"] != first["handler"]["decision"]
    grades = [claim["judge"]["grade"] for claim in weakest]
    assert grades == sorted(grades)
    assert set(view["objectives_on_the_held_out_set"]) == {"accuracy", "grade"}
    assert view["noise"]["accuracy"] == 0.1
    assert view["tolerance"]["cost_per_claim"] == 1.0
    assert view["rule"].startswith("A new version is kept")
    assert view["spending_left"] == pytest.approx(0.5 - 30 * JUDGE_COST)
    assert [m["model"] for m in view["models_allowed"]][0] == LUNA
    assert view["earlier_rounds"] == []
    text = json.dumps(view)
    ids, summaries, reasons = held_out_secrets()
    assert not any(secret in text for secret in ids + summaries + reasons)


def test_the_improver_sees_the_earlier_rounds(client):
    first = a_round(client)
    approved_change(client, first)
    client.post(f"/api/rounds/{first}/finish", json={"stopped": False, "reason": ""})
    second = a_round(client)
    earlier = client.get(f"/api/rounds/{second}/view").json()["earlier_rounds"]
    assert [(r["round_id"], r["version_tried"]) for r in earlier] == [(first, 2)]
    assert earlier[0]["reason"] == CHANGE["reason"]
    assert earlier[0]["verdict"] == "rolled_back"


def luna_at_two_tenths_of_a_cent(client):
    """A round whose first evaluations cost $0.002 a claim on Luna, $0.05 for
    each set's 25 claims, all of it on the one claim each decides, with $0.10
    of its limit left after them."""
    spent = 3 * 0.05 + 3 * JUDGE_COST
    settings_with(client, spending_limit=round(spent + 0.10, 6))
    round_id = a_round(client)
    first_evaluations(client, round_id, right=0.04, cost=0.05)
    return round_id


def test_a_round_that_cant_afford_a_versions_evaluations_rolls_it_back(client):
    round_id = luna_at_two_tenths_of_a_cent(client)
    worked = client.get(f"/api/rounds/{round_id}").json()
    assert worked["spending_limit"] - worked["spent"] == pytest.approx(0.10)
    approved_change(client, round_id)
    refused = evaluate(client, round_id, "evaluation")
    assert refused.status_code == 409
    assert refused.json()["detail"] == (
        "The evaluations could cost about $0.15, and $0.10 of the round's limit is left"
    )
    verdict = client.post(f"/api/rounds/{round_id}/verdict").json()
    assert (verdict["kept"], verdict["why"]) == (
        False,
        "the round couldn't afford to evaluate it",
    )
    assert client.get("/api/configuration").json()["current"] == 1


def test_a_model_with_no_runs_is_estimated_from_the_current_models_prices(client):
    luna_at_two_tenths_of_a_cent(client)
    with db.engine().connect() as conn:
        assert spending.per_claim(conn, LUNA, LUNA) == pytest.approx(0.002)
        assert spending.per_claim(conn, GEMINI, LUNA) == pytest.approx(0.010)


def test_a_spent_limit_refuses_the_next_copy_and_stops_the_evaluation(client):
    settings_with(client, spending_limit=0.01)
    round_id = a_round(client)
    run = client.post(
        f"/api/runs/rounds/{round_id}/evaluations",
        json={"evaluation_set": "evaluation"},
    ).json()
    copies = [c["claim_id"] for c in run["claims"]]
    thread = {"run_id": run["run_id"], "thread_id": "t"}
    assert client.post(f"/api/claims/{copies[0]}/start", json=thread).status_code == 200
    call = {
        "thread_id": "t",
        "run_id": run["run_id"],
        "model": LUNA,
        "input_tokens": 1,
        "output_tokens": 1,
        "cost": 0.02,
        "seconds": 1.0,
    }
    client.post(f"/api/claims/{copies[0]}/model-calls", json=call)
    refused = client.post(f"/api/claims/{copies[1]}/start", json=thread)
    assert refused.status_code == 409
    assert refused.json()["detail"] == f"Round {round_id} has spent its limit of $0.01"
    finished = client.post(f"/api/runs/{run['run_id']}/finish", json={"stopped": False})
    assert finished.json()["status"] == "stopped"


def test_a_round_costs_its_improver_its_evaluations_and_the_judge(client):
    round_id = a_round(client)
    evaluate(client, round_id, "evaluation", right=0.2, cost=0.001)
    call = {
        "model": LUNA,
        "input_tokens": 1000,
        "output_tokens": 100,
        "cost": 0.003,
        "seconds": 2.0,
    }
    recorded = client.post(f"/api/rounds/{round_id}/improver-calls", json=call)
    assert recorded.json()["round_id"] == round_id
    worked = client.get(f"/api/rounds/{round_id}").json()
    assert worked["spent"] == pytest.approx(5 * 0.001 + 0.003 + 5 * JUDGE_COST)
