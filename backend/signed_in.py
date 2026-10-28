"""The handler signed in, for the routes a handler's action goes through: who
the access token belongs to, and whether they may take an action only a
handler who can sign off payouts over the limit takes. The token is checked
before any database connection is taken, and the handler is found on a short
connection of its own, so a route that goes on to call the agent's service
holds none while it waits."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend import auth, db
from backend.claim_rules import approval_limit
from backend.models import Handler
from backend.seed import ready
from backend.store import records

# A missing bearer token is ours to refuse, with a 401
bearer = HTTPBearer(auto_error=False)
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def signed_in_email(credentials: Credentials) -> str:
    """The email a valid access token was issued to, or a 401."""
    email = auth.signed_in_email(credentials.credentials) if credentials else None
    if email is None:
        raise HTTPException(
            401, "Sign in as a handler first", {"WWW-Authenticate": "Bearer"}
        )
    return email


def signed_in(email: Annotated[str, Depends(signed_in_email)]) -> Handler:
    """The handler with the token's email, or a 403 when no handler has it."""
    engine = db.engine()
    ready(engine)
    with engine.connect() as conn:
        record = records.handler_by_email(conn, email)
    if record is None:
        raise HTTPException(403, f"{email} isn't one of UnderCover's handlers")
    return Handler.model_validate_json(record)


SignedIn = Annotated[Handler, Depends(signed_in)]


def refuse_unless_senior(handler: Handler, action: str, limit: float) -> None:
    """Refuse a handler who can't sign off payouts over the limit, saying what
    they can't do."""
    if not handler.can_approve_over_limit:
        raise HTTPException(
            403,
            "Only a handler who can sign off payouts over"
            f" ${limit:,.2f} can {action}. {handler.name} can't.",
        )


def senior(action: str) -> Any:
    """A dependency for the signed-in handler, who must be able to sign off
    payouts over the limit to take the action."""

    def senior_handler(handler: SignedIn) -> Handler:
        if not handler.can_approve_over_limit:
            with db.engine().connect() as conn:
                limit = approval_limit(conn)
            refuse_unless_senior(handler, action, limit)
        return handler

    return Depends(senior_handler)
