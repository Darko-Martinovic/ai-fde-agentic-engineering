"""The agent's connection to the backend at UNDERCOVER_API, which its two
clients share: `api.py`, the claim agent's, and `improver_api.py`, the
improver's. A refusal raises Refused; any other error raises httpx's."""

import json
from typing import Any

import httpx

from settings import setting

# Connections refused before the backend is up, as when npm run dev starts it
# beside the agent's service, are tried again this many times
CONNECT_RETRIES = 5


def client() -> httpx.Client:
    """Return a client for the backend at UNDERCOVER_API."""
    return httpx.Client(
        base_url=setting("UNDERCOVER_API"),
        timeout=30,
        transport=httpx.HTTPTransport(retries=CONNECT_RETRIES),
    )


class Refused(Exception):
    """The backend refused a request, with its status and its reason."""

    def __init__(self, status: int, detail: object) -> None:
        # FastAPI's detail is a message, or a list of errors for invalid input
        reason = detail if isinstance(detail, str) else json.dumps(detail)
        super().__init__(f"Refused ({status}): {reason}")
        self.status = status
        self.detail = detail


def send(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    query: dict[str, str] | None = None,
) -> httpx.Response:
    with client() as backend:
        response = backend.request(method, path, json=body, params=query)
    if response.is_client_error:
        raise Refused(response.status_code, response.json()["detail"])
    return response.raise_for_status()
