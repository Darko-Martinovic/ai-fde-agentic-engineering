"""Rounds of improvement played out through the API, as the agent's service,
the improver and its claim agents would, for the backend's tests. A share of
an evaluation's copies is decided as the handlers decided, read through the
store, and the rest are left undecided, so wrong, which keeps the tests quick."""

from backend import db
from backend.store import evaluations
from backend.tests.sign_ins import DANA, headers
from backend.tests.workflow_steps import decide

DANA_ID = "HND-01"
MARCUS_ID = "HND-02"
LUNA = "openai/gpt-6-luna"
CHANGE = {
    "instructions": "# A better claim agent\n\nDecide the claim with care.",
    "model": LUNA,
    "reasoning_effort": "low",
    "reason": "Fewer wrong referrals.",
}
RECIPE = {"recipe": "1. Read the results.\n2. Propose a change.", "reason": "Shorter."}
# The first evaluations a version needs, and the evaluations of a change
SETS = ["evaluation", "held_out", "held_out"]


def answer_key(evaluation_set):
    with db.engine().connect() as conn:
        return evaluations.handler_decisions(conn, evaluation_set)


def create_round(client, handler_id=DANA_ID, thread_id="improver-test"):
    body = {"handler_id": handler_id, "thread_id": thread_id}
    return client.post("/api/rounds", json=body)


def a_round(client):
    return create_round(client).json()["round_id"]


def model_call(client, copy_id, run_id, cost):
    call = {
        "thread_id": f"{copy_id}-t",
        "run_id": run_id,
        "model": LUNA,
        "input_tokens": 100,
        "output_tokens": 10,
        "cost": cost,
        "seconds": 1.0,
    }
    client.post(f"/api/claims/{copy_id}/model-calls", json=call)


def work(client, run, right, cost):
    """Decide the first `right` share of a running evaluation's copies as the
    handlers did, each costing `cost`, and leave the rest; a copy refused its
    start is left too."""
    key = answer_key(run["evaluation_set"])
    copies = [c["claim_id"] for c in run["claims"]]
    for copy_id in copies[: round(len(copies) * right)]:
        thread = {"run_id": run["run_id"], "thread_id": f"{copy_id}-t"}
        if client.post(f"/api/claims/{copy_id}/start", json=thread).status_code != 200:
            continue
        if cost:
            model_call(client, copy_id, run["run_id"], cost)
        expected = key[copy_id.rsplit("-E", 1)[0]]
        decide(client, copy_id, expected["decision"], expected["payout"])


def started(client, round_id, evaluation_set):
    """Create a round's next evaluation of a set."""
    return client.post(
        f"/api/runs/rounds/{round_id}/evaluations",
        json={"evaluation_set": evaluation_set},
    )


def finish_run(client, run, stopped=False):
    return client.post(f"/api/runs/{run['run_id']}/finish", json={"stopped": stopped})


def evaluate(client, round_id, evaluation_set, right=0.0, cost=0.0):
    """Create a round's next evaluation of a set, work it and finish it;
    return the finished run, or the refusal of its creation."""
    created = started(client, round_id, evaluation_set)
    if created.status_code != 200:
        return created
    work(client, created.json(), right, cost)
    return finish_run(client, created.json())


def first_evaluations(client, round_id, right=0.0, cost=0.0):
    for evaluation_set in SETS:
        evaluate(client, round_id, evaluation_set, right, cost)


def propose(client, round_id, change=CHANGE):
    return client.post(f"/api/rounds/{round_id}/proposals/changes", json=change)


def propose_recipe(client, round_id, recipe=RECIPE):
    return client.post(f"/api/rounds/{round_id}/proposals/recipes", json=recipe)


def review(client, round_id, proposal_id, **reviewed):
    """A handler's review of a proposal, Dana's approval unless told otherwise."""
    return client.post(
        f"/api/rounds/{round_id}/proposals/{proposal_id}/review",
        json={"handler_id": DANA_ID, "approved": True, "note": ""} | reviewed,
    )


def approved_change(client, round_id, change=CHANGE):
    """A change proposed, approved and made the version under test."""
    proposal_id = propose(client, round_id, change).json()["proposal_id"]
    review(client, round_id, proposal_id)
    return client.post(f"/api/rounds/{round_id}/versions").json()


def tried(client, round_id, right=0.8, cost=0.0):
    """The version under test evaluated, once and twice, and judged."""
    for evaluation_set in SETS:
        evaluate(client, round_id, evaluation_set, right, cost)
    return client.post(f"/api/rounds/{round_id}/verdict")


def finish(client, round_id, stopped=False, reason=""):
    body = {"stopped": stopped, "reason": reason}
    return client.post(f"/api/rounds/{round_id}/finish", json=body)


def stop(client, round_id, email=DANA):
    return client.post(
        f"/api/improvement/rounds/{round_id}/stop", headers=headers(email)
    )


def settings_with(client, **changes):
    """Change the platform's settings as Dana, keeping the rest."""
    now = client.get("/api/settings").json()["settings"]
    keep = {
        name: now[name]
        for name in (
            "approval_limit",
            "objectives",
            "noise",
            "tolerance",
            "spending_limit",
            "agents",
        )
    }
    return client.put("/api/settings", json=keep | changes, headers=headers(DANA))
