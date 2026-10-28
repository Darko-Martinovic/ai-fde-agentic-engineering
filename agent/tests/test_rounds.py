"""Rounds of improvement through the agent's service, on a stub improver and
stub claim agents, with their progress saved in memory: the first
evaluations, the improver's proposals and a handler's reviews, the version
tried and its verdict, the recipe, and the lock a round holds while it works."""

from functools import partial
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import Field

from agent import (
    api,
    dispatcher,
    harness,
    improver_api,
    rounds,
    service,
    versions,
)
from agent import improver as the_improver
from agent.tests.round_stubs import (
    CLAIM_COST,
    IMPROVER_COST,
    Improver,
    as_the_handlers,
    claim_agents,
    declines,
    improver,
    says,
)
from backend import db
from backend.store import rounds as stored_rounds
from backend.tests.round_steps import CHANGE, RECIPE, settings_with
from backend.tests.sign_ins import DANA, headers

DANA_ID = "HND-01"
JUDGE_COST = 0.00002


def finished_as_is(run):
    """An evaluation finished with its copies left as they are, undecided."""
    api.finish_run(run["run_id"], False)


@pytest.fixture
def round_service(backend, memory_saver, monkeypatch):
    """The service without its lifespan, working rounds on the improver and
    claim agents each test gives, and the tests' saver. Its background work
    runs before each request returns. Evaluations are finished as they stand
    unless a test gives claim agents to work them."""
    monkeypatch.setattr(service, "in_background", lambda work, *args: work(*args))
    models = {"improver": improver(), "claims": None}

    def evaluate(run):
        if models["claims"] is None:
            finished_as_is(run)
            return
        version = versions.version(api.get_version(run["version"]))
        work = partial(
            harness.work_in_run,
            version=version,
            new_saver=lambda: memory_saver,
            llm=models["claims"](run["version"]),
        )
        dispatcher.work_run(run, work, service.RESUMING, service.STOP)

    service.app.dependency_overrides[service.round_workers] = lambda: (
        rounds.RoundWorkers(
            model_for=lambda model: models["improver"],
            new_saver=lambda: memory_saver,
            evaluate=evaluate,
        )
    )
    service.app.dependency_overrides[service.savers] = lambda: lambda: memory_saver
    yield TestClient(service.app), models
    service.app.dependency_overrides.clear()


def start(client):
    return client.post("/api/rounds", json={"handler_id": DANA_ID})


def review(client, round_id, proposal_id, approved=True, note=""):
    body = {"handler_id": DANA_ID, "approved": approved, "note": note}
    path = f"/api/rounds/{round_id}/proposals/{proposal_id}/review"
    return client.post(path, json=body)


def the_round(backend, round_id=1):
    return backend.get(f"/api/rounds/{round_id}").json()


def proposals(round_id=1):
    with db.engine().connect() as conn:
        return stored_rounds.round_proposals(conn, round_id)


def evaluations_of(backend, round_id=1):
    listed = backend.get("/api/evaluations").json()
    return [run for run in reversed(listed) if run["round_id"] == round_id]


def test_a_round_runs_its_first_evaluations_and_waits_for_a_handler(
    backend, round_service
):
    client, models = round_service
    models["improver"] = improver(
        says("read_results"), says("propose_change", **CHANGE)
    )
    assert start(client).json() == {"round_id": 1}
    evaluated = evaluations_of(backend)
    assert [run["evaluation_set"] for run in evaluated] == [
        "evaluation",
        "held_out",
        "held_out",
    ]
    assert {run["version"] for run in evaluated} == {1}
    waiting = the_round(backend)
    assert (waiting["status"], waiting["stage"]) == ("open", "change_waiting")
    assert waiting["waiting"]["proposed"]["model"] == CHANGE["model"]
    assert waiting["waiting"]["reason"] == CHANGE["reason"]
    assert not service.RUNNING.locked()
    shown = models["improver"].shown
    assert "# Your recipe" in shown[0][0].content
    assert '"current_version"' in shown[1][-1].content


def test_a_round_tries_a_change_a_handler_approved_and_keeps_it(backend, round_service):
    client, models = round_service
    settings_with(
        backend,
        tolerance={
            "accuracy": 0.1,
            "grade": 0.15,
            "cost_per_claim": 1.0,
            "seconds_per_claim": 100.0,
        },
    )
    agents = {1: claim_agents(declines), 2: claim_agents(as_the_handlers)}
    models["claims"] = agents.get
    second = CHANGE | {"reason": "Fewer wrong referrals, said plainly."}
    models["improver"] = improver(
        says("read_results"),
        says("propose_change", **CHANGE),
        says("propose_change", **second),
        says("run_evaluation"),
        says("propose_recipe", **RECIPE),
        says(),
    )
    start(client)
    (first,) = proposals()
    review(client, 1, first["proposal_id"], approved=False, note="Too vague.")
    assert "Too vague." in models["improver"].shown[2][-1].content
    assert the_round(backend)["waiting"]["reason"] == second["reason"]
    review(client, 1, proposals()[-1]["proposal_id"])
    tried = the_round(backend)
    assert (tried["version_tried"], tried["verdict"]) == (2, "kept")
    assert tried["stage"] == "recipe_waiting"
    evaluated = evaluations_of(backend)
    assert [(r["version"], r["evaluation_set"]) for r in evaluated[3:]] == [
        (2, "evaluation"),
        (2, "held_out"),
        (2, "held_out"),
    ]
    assert {r["agents"] for r in evaluated} == {25}
    assert "Kept version 2" in models["improver"].shown[4][-1].content
    review(client, 1, proposals()[-1]["proposal_id"])
    done = the_round(backend)
    assert done["status"] == "finished"
    improvement = backend.get("/api/improvement").json()
    assert improvement["current_recipe"] == 2
    assert backend.get("/api/configuration").json()["current"] == 2
    claim_calls = len(agents[1].asked) + len(agents[2].asked)
    judged = sum(
        c["grade"] is not None and c["decision"] is not None
        for run in evaluated
        for c in backend.get(f"/api/evaluations/{run['run_id']}").json()["claims"]
    )
    assert done["spent"] == pytest.approx(
        6 * IMPROVER_COST + claim_calls * CLAIM_COST + judged * JUDGE_COST
    )


def test_a_change_to_a_model_not_allowed_goes_back_and_records_nothing(
    backend, round_service
):
    client, models = round_service
    models["improver"] = improver(
        says("propose_change", **(CHANGE | {"model": "openai/gpt-7"})), says()
    )
    start(client)
    assert "isn't allowed" in models["improver"].shown[1][-1].content
    assert proposals() == []
    assert the_round(backend)["status"] == "finished"


def test_one_thing_works_at_a_time_and_a_waiting_round_holds_nothing(
    backend, round_service, monkeypatch
):
    client, models = round_service
    models["improver"] = improver(says("propose_change", **CHANGE))
    with service.RUNNING.held("An evaluation is running"):
        refused = start(client)
    assert (refused.status_code, refused.json()["detail"]) == (
        409,
        "An evaluation is running",
    )
    assert backend.get("/api/improvement").json()["rounds"] == []
    start(client)
    proposal_id = proposals()[0]["proposal_id"]
    with service.RUNNING.held("A dispatch is running"):
        busy = review(client, 1, proposal_id)
    assert (busy.status_code, busy.json()["detail"]) == (409, "A dispatch is running")
    assert proposals()[0]["review"] is None
    monkeypatch.setattr(
        dispatcher, "work_run", lambda run, work, resuming, stop: finished_as_is(run)
    )
    assert client.post("/api/dispatches", json={"agents": 3}).status_code == 202
    assert the_round(backend)["stage"] == "change_waiting"


def test_a_waiting_round_survives_a_restart_and_carries_on_when_approved(
    backend, round_service
):
    client, models = round_service
    models["improver"] = improver(
        says("propose_change", **CHANGE), says("propose_recipe", **RECIPE)
    )
    start(client)
    with TestClient(service.app) as restarted:
        assert the_round(backend)["status"] == "open"
        review(restarted, 1, proposals()[0]["proposal_id"])
    assert the_round(backend)["stage"] == "recipe_waiting"
    assert the_round(backend)["version_tried"] == 2


def test_a_restart_stops_a_round_in_its_first_evaluations(backend, round_service):
    client, _ = round_service
    api_round = improver_api.create_round(DANA_ID, "improver-restart")["round_id"]
    with TestClient(service.app):
        pass
    stopped = the_round(backend, api_round)
    assert stopped["status"] == "stopped"
    assert "restarted" in stopped["stop_reason"]


def test_stopping_a_round_in_its_evaluations_starts_nothing_more(
    backend, round_service
):
    client, models = round_service
    settings_with(backend, agents=1)

    def stops_on_the_second(claim_id):
        if len(agents.asked) == 2:
            backend.post("/api/improvement/rounds/1/stop", headers=headers(DANA))
        return declines(claim_id)

    agents = claim_agents(stops_on_the_second)
    models["claims"] = lambda version: agents
    models["improver"] = improver(says())
    start(client)
    assert len(agents.asked) == 2
    assert the_round(backend)["status"] == "stopped"
    assert evaluations_of(backend)[0]["status"] == "stopped"
    assert len(evaluations_of(backend)) == 1
    assert models["improver"].shown == []
    assert not service.RUNNING.locked()


def test_the_improver_stops_after_20_calls_across_an_approval(backend, round_service):
    client, models = round_service
    models["improver"] = improver(
        says("propose_change", **CHANGE), *[says("read_results") for _ in range(25)]
    )
    start(client)
    review(client, 1, proposals()[0]["proposal_id"])
    stopped = the_round(backend)
    assert len(models["improver"].shown) == 20
    assert stopped["status"] == "stopped"
    assert "limit" in stopped["stop_reason"].lower()
    assert backend.get("/api/configuration").json()["current"] == 1


def test_a_round_with_no_proposal_finishes_with_none_tried(backend, round_service):
    client, models = round_service
    models["improver"] = improver(says("read_results"), says())
    start(client)
    done = the_round(backend)
    assert (done["status"], done["version_tried"]) == ("finished", None)
    assert done["spent"] == pytest.approx(2 * IMPROVER_COST)


def test_a_limit_spent_in_the_first_evaluations_stops_the_round_first(
    backend, round_service
):
    client, models = round_service
    settings_with(backend, agents=1, spending_limit=0.00015)
    agents = claim_agents(declines)
    models["claims"] = lambda version: agents
    start(client)
    stopped = the_round(backend)
    assert stopped["status"] == "stopped"
    assert stopped["stop_reason"] == rounds.SPENT_FIRST
    assert len(agents.asked) == 2
    assert models["improver"].shown == []


def test_a_round_is_stopped_only_as_a_round(backend, round_service):
    client, _ = round_service
    with service.RUNNING.held("Round 3 is running", round_=True):
        refused = client.post("/api/runs/stop")
    assert (refused.status_code, refused.json()["detail"]) == (
        409,
        "Round 3 is running: stop it on the Improvement page",
    )
    assert not service.STOP.is_set()


class Binding(Improver):
    """The improver's model, keeping what it was bound with."""

    bound: list[dict[str, Any]] = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        self.bound.append(kwargs)
        return self


@pytest.mark.parametrize(
    ("provider", "settings"),
    [("openrouter", {"parallel_tool_calls": False}), ("ollama", {})],
)
def test_one_tool_call_at_a_time_is_asked_only_of_a_provider_that_takes_it(
    backend, memory_saver, provider, settings
):
    round_id = improver_api.create_round(DANA_ID, "improver-bound")["round_id"]
    model = Binding(messages=iter([says()]))
    context = the_improver.RoundContext(
        round_id=round_id,
        model="a-model",
        provider=provider,
        models_allowed=[],
        evaluate=finished_as_is,
    )
    agent = the_improver.improver(model, "Improve.", memory_saver)
    the_improver.work_stretch(agent, context, "improver-bound", None, {})
    assert [
        {k: v for k, v in bound.items() if k == "parallel_tool_calls"}
        for bound in model.bound
    ] == [settings]
