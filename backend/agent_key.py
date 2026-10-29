"""The agent's key: every request from the agent's side carries it in the
X-API-Key header, and the routes only the agent's side calls refuse a request
without it. With no UNDERCOVER_API_KEY set, every key is wrong."""

import secrets
from typing import Annotated

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from settings import optional_setting

KEY_HEADER = "X-API-Key"
NEEDS_THE_KEY = "This route needs the agent's key"

# A missing key is ours to refuse, with a 401
key_header = APIKeyHeader(name=KEY_HEADER, auto_error=False)
Key = Annotated[str | None, Security(key_header)]


def is_agent(key: str | None) -> bool:
    """Whether a request's key is the agent's, compared in constant time."""
    expected = optional_setting("UNDERCOVER_API_KEY")
    if expected is None or key is None:
        return False
    return secrets.compare_digest(key.encode(), expected.encode())


def agent_key(key: Key) -> None:
    """Refuse a request without the agent's key with a 401."""
    if not is_agent(key):
        raise HTTPException(401, NEEDS_THE_KEY)
