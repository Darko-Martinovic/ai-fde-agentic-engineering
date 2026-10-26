"""The backend's one call to the agent's service, at UNDERCOVER_AGENT: asking it
to pick a claim back up after a handler's review. A review stands whether or not
the service can be reached; the next run of the agent carries the claim on."""

import logging

import httpx

from settings import setting

log = logging.getLogger(__name__)


def resume_claim(claim_id: str) -> None:
    """Ask the agent's service to pick the claim back up."""
    try:
        httpx.post(
            f"{setting('UNDERCOVER_AGENT')}/api/claims/{claim_id}/resume", timeout=10
        ).raise_for_status()
    except httpx.HTTPError as error:
        log.warning("The agent's service didn't pick up %s: %s", claim_id, error)
