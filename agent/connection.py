"""The agent's connection to the backend at UNDERCOVER_API, which its clients
share. Every request carries the agent's key, UNDERCOVER_API_KEY, in the
X-API-Key header. A refusal raises Refused; any other error raises httpx's."""

import json
from typing import Any

import httpx

from settings import optional_setting, setting

KEY_HEADER = "X-API-Key"
KEY_SETTING = "UNDERCOVER_API_KEY"
NO_KEY = f"{KEY_SETTING} is missing: add the agent's key to .env"

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


def require_key() -> None:
    """Refuse to go on without the agent's key, saying it's missing."""
    if optional_setting(KEY_SETTING) is None:
        raise RuntimeError(NO_KEY)


def send(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    query: dict[str, str] | None = None,
) -> httpx.Response:
    # Read as each request is sent: the command line loads .env after it starts
    key = optional_setting(KEY_SETTING)
    with client() as backend:
        response = backend.request(
            method,
            path,
            json=body,
            params=query,
            headers={KEY_HEADER: key} if key else None,
        )
    if response.is_client_error:
        raise Refused(response.status_code, response.json()["detail"])
    return response.raise_for_status()
