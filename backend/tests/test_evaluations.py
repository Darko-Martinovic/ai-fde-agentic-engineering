import httpx
import pytest

from backend import agent_service, seed
from backend.tests.sign_ins import DANA, MARCUS, headers
from backend.tests.workflow_steps import decide, fail, pay

LUNA = "openai/gpt-6-luna"
AS_MARCUS = headers(MARCUS)
HELD_OUT_TINY = ["CLM-1114", "CLM-1106", "CLM-1112", "CLM-1104", "CLM-1110"]


def create(client, evaluation_set="held_out", tiny=True, agents=5):
    body = {
        "evaluation_set": evaluation_set,
        "tiny": tiny,
        "agents": agents,
    }
    return client.post("/api/runs/evaluations", json=body)


def test_an_evaluation_makes_waiting_copies_of_a_sets_tiny_claims(client):
    run = create(client).json()
    assert (run["kind"], run["evaluation_set"], run["tiny"]) == (
        "evaluation",
        "held_out",
        True,
    )
    assert (run["agents"], run["version"], run["model"], run["reasoning_effort"]) == (
        5,
        1,
        LUNA,
        "low",
    )
    copies = [c["claim_id"] for c in run["claims"]]
    assert copies == [f"{claim_id}-E1" for claim_id in HELD_OUT_TINY]
    for copy_id in copies:
        claim = client.get(f"/api/claims/{copy_id}").json()
        assert (claim["claim_id"], claim["status"]) == (copy_id, "waiting")
        assert (claim["evaluation_id"], claim["copy_of"]) == (1, copy_id[:-3])


def test_a_whole_set_makes_25_copies_and_an_unknown_set_is_refused(client):
    assert len(create(client, "evaluation", tiny=False).json()["claims"]) == 25
    assert create(client, "harder").status_code == 422


def test_the_queue_and_insights_leave_the_copies_out(client):
    queue = client.get("/api/claims").json()
    insights = client.get("/api/insights").json()
    run = create(client, "evaluation", tiny=False).json()
    copy_id = run["claims"][0]["claim_id"]
    client.post(
        f"/api/claims/{copy_id}/start", json={"run_id": run["run_id"], "thread_id": "t"}
    )
    decide(client, copy_id, "approve", 420.0)
    pay(client, copy_id, 420.0)
    step = {"thread_id": "t", "kind": "tool_call", "text": "get_claim {}"}
    client.post(f"/api/claims/{copy_id}/steps", json=step)
    assert client.get("/api/claims").json() == queue
    assert client.get("/api/insights").json() == insights
    assert client.get("/api/claims/CLM-1001").json()["evaluation_id"] is None


def handlers_words(evaluation_set):
    """What the handlers wrote on a set's claims: their reasons, references and
    calculations."""
    decisions = seed.read(seed.HANDLER_DECISIONS[evaluation_set], seed.ANSWER_KEY)
    return [
        str(decision[field])
        for decision in decisions
        for field in ("reason", "reference", "calculation")
        if decision.get(field)
    ]


@pytest.mark.parametrize("evaluation_set", ["evaluation", "held_out"])
def test_nothing_the_agent_reads_holds_the_handlers_decisions(client, evaluation_set):
    made = create(client, evaluation_set, tiny=False)
    seen = [made.text] + [
        client.get(f"/api/claims/{copy['claim_id']}").text
        for copy in made.json()["claims"]
    ]
    words = handlers_words(evaluation_set)
    assert words
    assert not [w for w in words for text in seen if w in text]
    for text in seen:
        assert '"handler_decision"' not in text


def held_copy(client):
    """The copy of CLM-1112 approved for $1,200.00, held for sign-off."""
    run = create(client).json()
    client.post(
        "/api/claims/CLM-1112-E1/start",
        json={"run_id": run["run_id"], "thread_id": "CLM-1112-E1-t"},
    )
    decide(client, "CLM-1112-E1", "approve", 1200.0)
    return run


@pytest.mark.parametrize("approved", [True, False])
def test_nobody_can_review_a_copy(client, approved, resumed):
    held_copy(client)
    body = {"approved": approved, "note": "Too much."}
    refused = client.post(
        "/api/claims/CLM-1112-E1/review", json=body, headers=headers(DANA)
    )
    assert refused.status_code == 409
    assert refused.json()["detail"] == (
        "Claim CLM-1112-E1 is a copy in an evaluation and can't be reviewed or decided"
    )
    claim = client.get("/api/claims/CLM-1112-E1").json()
    assert claim["status"] == "awaiting_sign_off"
    assert claim["decisions"][-1]["review"] is None
    assert resumed == []


def play_out(client):
    """The held-out set's tiny claims, as the agent might work them: CLM-1104
    approved for $250.00 and paid, CLM-1106 approved for $300.00 and paid,
    CLM-1110 referred, CLM-1112 approved for $1,200.00 and held, and CLM-1114
    never decided; each with a model call of $0.0125 and 40 seconds of work."""
    run_id = held_copy(client)["run_id"]
    for claim_id, decision, payout in [
        ("CLM-1104", "approve", 250.0),
        ("CLM-1106", "approve", 300.0),
        ("CLM-1110", "refer", 0),
        ("CLM-1114", None, 0),
    ]:
        copy_id = f"{claim_id}-E1"
        client.post(
            f"/api/claims/{copy_id}/start",
            json={"run_id": run_id, "thread_id": f"{copy_id}-t"},
        )
        if decision:
            decide(client, copy_id, decision, payout)
        if decision == "approve":
            pay(client, copy_id, payout)
    for claim_id in HELD_OUT_TINY:
        copy_id = f"{claim_id}-E1"
        spell = {"thread_id": f"{copy_id}-t", "run_id": run_id, "seconds": 40}
        call = spell | {
            "model": LUNA,
            "input_tokens": 1000,
            "output_tokens": 100,
            "cost": 0.0125,
        }
        client.post(f"/api/claims/{copy_id}/model-calls", json=call)
        client.post(f"/api/claims/{copy_id}/work-times", json=spell)
    client.post(f"/api/runs/{run_id}/finish", json={"stopped": False})
    return run_id


def test_an_evaluation_is_scored_from_its_records(client):
    run_id = play_out(client)
    evaluation = client.get(f"/api/evaluations/{run_id}").json()
    assert evaluation["measures"] == pytest.approx(
        {
            "decision_accuracy": 0.8,
            "accuracy": 0.4,
            "cost_of_mistakes": 50 + 520 + 50,
            "straight_through": 0.6,
            "model_cost_per_claim": 0.0125,
            "seconds_per_claim": 40,
            "run_seconds": evaluation["measures"]["run_seconds"],
            # Four decided copies graded B (2.2), and CLM-1114 an F unasked
            "grade": (4 * 2.2 + 0) / 5,
            "judge_cost": 4 * 0.00002,
        }
    )
    assert evaluation["measures"]["run_seconds"] >= 0
    assert evaluation["status"] == "finished"
    by_copy = {c["copy_of"]: c for c in evaluation["claims"]}
    assert by_copy["CLM-1104"]["right"] is True
    assert (by_copy["CLM-1112"]["right"], by_copy["CLM-1112"]["mistake_cost"]) == (
        False,
        520,
    )
    assert (by_copy["CLM-1114"]["decision"], by_copy["CLM-1114"]["mistake_cost"]) == (
        None,
        50,
    )
    assert by_copy["CLM-1106"]["handler_payout"] == 250.0
    assert by_copy["CLM-1104"]["reasons"] == "The agent's reasons to approve."


def test_the_scoreboard_lists_evaluations_newest_first(client):
    first = create(client).json()["run_id"]
    client.post(
        "/api/runs/dispatches",
        json={"agents": 3},
    )
    second = create(client, "evaluation").json()["run_id"]
    listed = client.get("/api/evaluations").json()
    assert [e["run_id"] for e in listed] == [second, first]
    assert listed[1]["measures"]["straight_through"] == 0


def test_a_dispatch_isnt_an_evaluation(client):
    client.post(
        "/api/runs/dispatches",
        json={"agents": 3},
    )
    assert client.get("/api/evaluations/1").status_code == 404
    assert client.get("/api/evaluations/99").status_code == 404


@pytest.fixture
def service(monkeypatch):
    asked = []

    def post(url, json, timeout):
        asked.append((url.removeprefix(agent_service.url("")), json))
        if json.get("agents") == 9:
            raise httpx.ConnectError("refused")
        if json.get("agents") == 8:
            return httpx.Response(
                409, json={"detail": "A dispatch or an evaluation is already running"}
            )
        return httpx.Response(202, json={"agents": json["agents"]})

    monkeypatch.setattr(agent_service.httpx, "post", post)
    return asked


def test_a_start_passes_the_set_and_n_on_to_the_service(client, service):
    body = {"evaluation_set": "held_out", "tiny": True, "agents": 5}
    started = client.post("/api/evaluations", headers=AS_MARCUS, json=body)
    assert started.status_code == 202
    assert service == [("/api/evaluations", body)]
    assert client.get("/api/evaluations").json() == []
    busy = client.post("/api/evaluations", headers=AS_MARCUS, json=body | {"agents": 8})
    assert busy.status_code == 409
    down = client.post("/api/evaluations", headers=AS_MARCUS, json=body | {"agents": 9})
    assert (down.status_code, down.json()["detail"]) == (
        503,
        "The agent's service isn't running",
    )
    for bad in ({"agents": 0}, {"agents": 26}, {"evaluation_set": "harder"}):
        assert (
            client.post(
                "/api/evaluations", headers=AS_MARCUS, json=body | bad
            ).status_code
            == 422
        )
    assert len(service) == 3


def test_a_copys_record_is_the_original_with_its_own_id(client):
    create(client, "evaluation")
    copy = client.get("/api/claims/CLM-1007-E1").json()
    original = client.get("/api/claims/CLM-1007").json()
    assert copy["claim_id"] == "CLM-1007-E1"
    assert (copy["story"], copy["items"]) == (original["story"], original["items"])


@pytest.mark.parametrize("left", ["referred", "left_for_handler"])
def test_nobody_decides_a_copy_left_for_a_handler(client, left):
    run = create(client).json()
    copy_id = "CLM-1110-E1"
    client.post(
        f"/api/claims/{copy_id}/start",
        json={"run_id": run["run_id"], "thread_id": f"{copy_id}-t"},
    )
    if left == "referred":
        decide(client, copy_id, "refer", 0)
    else:
        fail(client, copy_id, thread_id=f"{copy_id}-t")
        client.post(
            f"/api/claims/{copy_id}/start",
            json={"run_id": run["run_id"], "thread_id": f"{copy_id}-t"},
        )
        fail(client, copy_id, thread_id=f"{copy_id}-t")
    assert client.get(f"/api/claims/{copy_id}").json()["status"] == left
    body = {
        "decision": "approve",
        "payout": 250.0,
        "reasons": "A handler's answer would score as the agent's.",
    }
    refused = client.post(
        f"/api/claims/{copy_id}/handler-decision", json=body, headers=headers(DANA)
    )
    assert refused.status_code == 409
    claim = client.get(f"/api/claims/{copy_id}").json()
    assert (claim["status"], claim["payment"]) == (left, None)


def test_an_evaluation_stopped_partway_shows_as_stopped(client):
    run_id = create(client).json()["run_id"]
    stopped = client.post(f"/api/runs/{run_id}/finish", json={"stopped": True})
    assert stopped.json()["status"] == "stopped"
    [listed] = client.get("/api/evaluations").json()
    assert (listed["status"], listed["measures"]["straight_through"]) == ("stopped", 0)


def test_a_dispatch_records_only_the_queues_claims(client):
    evaluation = create(client).json()
    refused = client.put(
        f"/api/runs/{evaluation['run_id']}/claims", json={"claim_ids": ["CLM-1001"]}
    )
    assert refused.status_code == 409
    dispatch = client.post(
        "/api/runs/dispatches",
        json={"agents": 3},
    ).json()
    copy = client.put(
        f"/api/runs/{dispatch['run_id']}/claims", json={"claim_ids": ["CLM-1104-E1"]}
    )
    assert copy.status_code == 409
    assert copy.json()["detail"] == "Claim CLM-1104-E1 is a copy in an evaluation"
