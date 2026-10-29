"""Policies and customers, as recorded."""

from fastapi import APIRouter

from backend.api import Db, found, load_policy
from backend.callers import AGENT_OR_HANDLER
from backend.models import Customer, Policy
from backend.store import records

router = APIRouter(prefix="/api")


@router.get(
    "/policies/{policy_id}", operation_id="get_policy", dependencies=[AGENT_OR_HANDLER]
)
def get_policy(policy_id: str, conn: Db) -> Policy:
    """Get one policy with its plan's limits and its add-ons."""
    return load_policy(conn, policy_id)


@router.get(
    "/customers/{customer_id}",
    operation_id="get_customer",
    dependencies=[AGENT_OR_HANDLER],
)
def get_customer(customer_id: str, conn: Db) -> Customer:
    """Get one customer with their claim history."""
    record = found(records.customer(conn, customer_id), "Customer", customer_id)
    return Customer.model_validate_json(record)
