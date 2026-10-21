"""Policies, customers and handlers, as recorded."""

import json
from typing import Any

from fastapi import APIRouter

from backend.api import Db, find, setting
from backend.models import Customer, Handler, Policy

router = APIRouter(prefix="/api")


@router.get("/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, conn: Db) -> Policy:
    """Get one policy with its plan's limits and its add-ons."""
    row = find(
        conn, "SELECT data FROM policies WHERE policy_id = ?", policy_id, "Policy"
    )
    policy: dict[str, Any] = json.loads(row["data"])
    plans = json.loads(setting(conn, "plans"))
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
    row = find(
        conn,
        "SELECT data FROM customers WHERE customer_id = ?",
        customer_id,
        "Customer",
    )
    return Customer.model_validate_json(row["data"])


@router.get("/handlers", operation_id="list_handlers")
def list_handlers(conn: Db) -> list[Handler]:
    """List the claims handlers."""
    rows = conn.execute("SELECT data FROM handlers ORDER BY handler_id").fetchall()
    return [Handler.model_validate_json(row["data"]) for row in rows]
