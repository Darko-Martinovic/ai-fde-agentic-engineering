"""Policies, customers and handlers, as recorded."""

import json
from typing import Any

from fastapi import APIRouter

from backend.api import Db, found
from backend.models import Customer, Handler, Policy
from backend.store import records

router = APIRouter(prefix="/api")


@router.get("/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, conn: Db) -> Policy:
    """Get one policy with its plan's limits and its add-ons."""
    policy: dict[str, Any] = found(records.policy(conn, policy_id), "Policy", policy_id)
    plans = json.loads(records.stored(conn, "plans"))
    plan = next(p for p in plans["plans"] if p["plan"] == policy["plan"])
    add_ons = [a for a in plans["add_ons"] if a["add_on"] in policy["add_ons"]]
    return Policy.model_validate(
        policy
        | {
            "plan": plan,
            "add_ons": add_ons,
            "deductible_applies_to": plans["deductible_applies_to"],
        }
    )


@router.get("/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str, conn: Db) -> Customer:
    """Get one customer with their claim history."""
    record = found(records.customer(conn, customer_id), "Customer", customer_id)
    return Customer.model_validate_json(record)


@router.get("/handlers", operation_id="list_handlers")
def list_handlers(conn: Db) -> list[Handler]:
    """List the claims handlers."""
    return [Handler.model_validate_json(record) for record in records.handlers(conn)]
