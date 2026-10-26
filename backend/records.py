"""Policies, customers and handlers, as recorded."""

from fastapi import APIRouter

from backend.api import Db, found, load_policy
from backend.models import Customer, Handler, Policy
from backend.store import records

router = APIRouter(prefix="/api")


@router.get("/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, conn: Db) -> Policy:
    """Get one policy with its plan's limits and its add-ons."""
    return load_policy(conn, policy_id)


@router.get("/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str, conn: Db) -> Customer:
    """Get one customer with their claim history."""
    record = found(records.customer(conn, customer_id), "Customer", customer_id)
    return Customer.model_validate_json(record)


@router.get("/handlers", operation_id="list_handlers")
def list_handlers(conn: Db) -> list[Handler]:
    """List the claims handlers."""
    return [Handler.model_validate_json(record) for record in records.handlers(conn)]
