"""The backend's API, as the model comparison uses it: starting an evaluation and
reading the scoreboard, at UNDERCOVER_API. The comparison reaches the backend
only through this module."""

from typing import Any

import httpx

from settings import setting


def client() -> httpx.Client:
    """Return a client for the backend at UNDERCOVER_API."""
    return httpx.Client(base_url=setting("UNDERCOVER_API"), timeout=30)


def start_evaluation(
    evaluation_set: str, tiny: bool, agents: int, model: str
) -> dict[str, Any]:
    """Ask the backend to start an evaluation, as the Scoreboard does."""
    body = {
        "evaluation_set": evaluation_set,
        "tiny": tiny,
        "agents": agents,
        "model": model,
    }
    with client() as backend:
        response = backend.post("/api/evaluations", json=body)
    return response.raise_for_status().json()


def list_evaluations() -> list[dict[str, Any]]:
    """Every evaluation, newest first, with its scores."""
    with client() as backend:
        return backend.get("/api/evaluations").raise_for_status().json()


def get_evaluation(run_id: int) -> dict[str, Any]:
    """One evaluation, with its scores and its copies."""
    with client() as backend:
        return backend.get(f"/api/evaluations/{run_id}").raise_for_status().json()
