"""The claims in the queue by state, as the agents find them through the API."""

from typing import Any

from agent import api


def claims_in(status: str) -> list[dict[str, Any]]:
    """Return the claims in one state, in claim id order."""
    return [claim for claim in api.list_claims() if claim["status"] == status]


def waiting_claims() -> list[dict[str, Any]]:
    """Return the claims waiting in the queue, in claim id order."""
    return claims_in("waiting")
