"""The backend's calls to the agent's service, at UNDERCOVER_AGENT: starting a
dispatch, an evaluation or a round of improvement, stopping a run, passing on a
handler's review of the improver's proposal, and asking the service to pick a
claim back up after a handler's review. A start or a stop passes the service's
refusal on, and says so when the service can't be reached; a review stands
whether or not the service can be reached, and the next dispatch carries the
claim on."""

import logging
from typing import Any

import httpx
from fastapi import HTTPException

from settings import setting

log = logging.getLogger(__name__)

NOT_RUNNING = "The agent's service isn't running"
FAILED = "The agent's service failed"
TIMEOUT_SECONDS = 10


def url(path: str) -> str:
    return f"{setting('UNDERCOVER_AGENT')}{path}"


def ask(path: str, body: dict[str, Any]) -> dict[str, Any]:
    """Ask the agent's service to do something, passing on its refusal (a 4xx).
    A service that can't be reached is a 503, and one that fails a 502."""
    try:
        response = httpx.post(url(path), json=body, timeout=TIMEOUT_SECONDS)
    except httpx.TimeoutException as error:
        raise HTTPException(502, FAILED) from error
    except httpx.TransportError as error:
        raise HTTPException(503, NOT_RUNNING) from error
    if response.is_client_error:
        raise HTTPException(response.status_code, response.json()["detail"])
    if response.is_error:
        raise HTTPException(502, FAILED)
    return response.json()


def start_dispatch(agents: int) -> dict[str, Any]:
    """Ask the agent's service to start a dispatch of the queue."""
    return ask("/api/dispatches", {"agents": agents})


def start_evaluation(evaluation_set: str, tiny: bool, agents: int) -> dict[str, Any]:
    """Ask the agent's service to start an evaluation of a labelled set."""
    body = {"evaluation_set": evaluation_set, "tiny": tiny, "agents": agents}
    return ask("/api/evaluations", body)


def stop_run() -> dict[str, Any]:
    """Ask the agent's service to stop the run it's working."""
    return ask("/api/runs/stop", {})


def start_round(handler_id: str) -> dict[str, Any]:
    """Ask the agent's service to start a round of improvement."""
    return ask("/api/rounds", {"handler_id": handler_id})


def review_proposal(
    round_id: int, proposal_id: int, handler_id: str, approved: bool, note: str
) -> dict[str, Any]:
    """Pass a handler's review of the improver's proposal to the agent's service."""
    body = {"handler_id": handler_id, "approved": approved, "note": note}
    return ask(f"/api/rounds/{round_id}/proposals/{proposal_id}/review", body)


def resume_claim(claim_id: str) -> None:
    """Ask the agent's service to pick the claim back up."""
    try:
        httpx.post(
            url(f"/api/claims/{claim_id}/resume"), timeout=TIMEOUT_SECONDS
        ).raise_for_status()
    except httpx.HTTPError as error:
        log.warning("The agent's service didn't pick up %s: %s", claim_id, error)
