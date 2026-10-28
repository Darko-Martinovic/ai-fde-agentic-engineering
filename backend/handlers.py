"""The claims handlers, and the one signed in."""

from fastapi import APIRouter

from backend.api import Db
from backend.models import Handler, HandlerName
from backend.signed_in import SignedIn
from backend.store import records

router = APIRouter(prefix="/api")


@router.get("/handlers", operation_id="list_handlers")
def list_handlers(conn: Db) -> list[HandlerName]:
    """List the claims handlers by name, for the decisions they sign."""
    return [
        HandlerName.model_validate_json(record) for record in records.handlers(conn)
    ]


@router.get("/me", operation_id="get_signed_in_handler")
def get_signed_in_handler(handler: SignedIn) -> Handler:
    """Get the handler signed in, with what they may do."""
    return handler
