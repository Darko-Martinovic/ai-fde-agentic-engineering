"""The records the claims refer to: policies, customers, handlers, and the
stored settings (the plans, the company's rules and the documents)."""

import json
from typing import Any

from sqlalchemy import Connection, select, update
from sqlalchemy import insert as insert_into

from backend import db


def policy(conn: Connection, policy_id: str) -> dict[str, Any] | None:
    found = select(db.policies.c.data).where(db.policies.c.policy_id == policy_id)
    data = conn.execute(found).scalar_one_or_none()
    return json.loads(data) if data else None


def customer(conn: Connection, customer_id: str) -> str | None:
    """Return a customer's record as JSON, or None if there's no such customer."""
    found = select(db.customers.c.data).where(db.customers.c.customer_id == customer_id)
    return conn.execute(found).scalar_one_or_none()


def handlers(conn: Connection) -> list[str]:
    """Return every handler's record as JSON, in id order."""
    found = select(db.handlers.c.data).order_by(db.handlers.c.handler_id)
    return list(conn.execute(found).scalars())


def handler_by_email(conn: Connection, email: str) -> str | None:
    """Return the record, as JSON, of the handler with this email, or None."""
    found = select(db.handlers.c.data).where(db.handlers.c.email == email.lower())
    return conn.execute(found).scalar_one_or_none()


def stored(conn: Connection, name: str) -> str:
    """Return one stored setting, such as the plans or the policy wording."""
    found = select(db.settings.c.value).where(db.settings.c.name == name)
    return conn.execute(found).scalar_one()


def store(conn: Connection, name: str, value: str) -> None:
    """Replace one stored setting, such as the company's rules."""
    conn.execute(
        update(db.settings).where(db.settings.c.name == name).values(value=value)
    )


def insert(
    conn: Connection,
    policies: list[dict[str, Any]],
    customers: list[dict[str, Any]],
    handler_records: list[dict[str, Any]],
    settings: dict[str, str],
) -> None:
    """Store the records seeded from data/."""
    conn.execute(
        insert_into(db.policies),
        [{"policy_id": p["policy_id"], "data": json.dumps(p)} for p in policies],
    )
    conn.execute(
        insert_into(db.customers),
        [{"customer_id": c["customer_id"], "data": json.dumps(c)} for c in customers],
    )
    conn.execute(
        insert_into(db.handlers),
        [
            {
                "handler_id": h["handler_id"],
                "email": h["email"].lower(),
                "data": json.dumps(h),
            }
            for h in handler_records
        ],
    )
    conn.execute(
        insert_into(db.settings),
        [{"name": name, "value": value} for name, value in settings.items()],
    )
