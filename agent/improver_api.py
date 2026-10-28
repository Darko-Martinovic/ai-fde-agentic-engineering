"""The backend's API, as the improver and the agent's service use it in a round
of improvement: one function per operation under /api/rounds, named after it,
and `create_round_evaluation`, through the connection in `connection.py`. The
claim agent never imports it, so it has no way to the scores or the handlers'
decisions."""

from typing import Any

from agent.connection import send


def create_round(handler_id: str, thread_id: str) -> dict[str, Any]:
    body = {"handler_id": handler_id, "thread_id": thread_id}
    return send("POST", "/api/rounds", body).json()


def stop_rounds() -> list[int]:
    return send("POST", "/api/rounds/stop-all").json()["round_ids"]


def get_round(round_id: int) -> dict[str, Any]:
    return send("GET", f"/api/rounds/{round_id}").json()


def get_improver_view(round_id: int) -> dict[str, Any]:
    return send("GET", f"/api/rounds/{round_id}/view").json()


def record_change_proposal(round_id: int, change: dict[str, Any]) -> dict[str, Any]:
    return send("POST", f"/api/rounds/{round_id}/proposals/changes", change).json()


def record_recipe_proposal(round_id: int, recipe: dict[str, Any]) -> dict[str, Any]:
    return send("POST", f"/api/rounds/{round_id}/proposals/recipes", recipe).json()


def record_review(
    round_id: int, proposal_id: int, review: dict[str, Any]
) -> dict[str, Any]:
    path = f"/api/rounds/{round_id}/proposals/{proposal_id}/review"
    return send("POST", path, review).json()


def create_version(round_id: int) -> dict[str, Any]:
    return send("POST", f"/api/rounds/{round_id}/versions").json()


def create_recipe(round_id: int) -> dict[str, Any]:
    return send("POST", f"/api/rounds/{round_id}/recipes").json()


def create_round_evaluation(round_id: int, evaluation_set: str) -> dict[str, Any]:
    body = {"evaluation_set": evaluation_set}
    return send("POST", f"/api/runs/rounds/{round_id}/evaluations", body).json()


def record_verdict(round_id: int) -> dict[str, Any]:
    return send("POST", f"/api/rounds/{round_id}/verdict").json()


def record_improver_call(round_id: int, call: dict[str, Any]) -> None:
    send("POST", f"/api/rounds/{round_id}/improver-calls", call)


def finish_round(round_id: int, stopped: bool, reason: str) -> dict[str, Any]:
    body = {"stopped": stopped, "reason": reason}
    return send("POST", f"/api/rounds/{round_id}/finish", body).json()
