"""Who may call a route, for its dependencies: the agent's side with its key,
a signed-in handler, or either. Every route takes one of these, or its handler
as SignedIn or senior(action), or nothing when it's open, as health is."""

from fastapi import Depends

from backend.agent_key import Key, agent_key, is_agent
from backend.signed_in import Credentials, signed_in, signed_in_email


def agent_or_handler(key: Key, credentials: Credentials) -> None:
    """Let the agent's side through with its key, and anyone else only once
    they've signed in as a handler. FastAPI has no dependency for one of two, so
    this calls the sign-in's own two in turn when the key isn't there."""
    if not is_agent(key):
        signed_in(signed_in_email(credentials))


# Only the agent's side calls it
AGENT = Depends(agent_key)
# A read both the dashboard and the agent use
AGENT_OR_HANDLER = Depends(agent_or_handler)
# Only a signed-in handler calls it
HANDLER = Depends(signed_in)
