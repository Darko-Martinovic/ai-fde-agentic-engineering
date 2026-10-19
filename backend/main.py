"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from backend import db
from backend.models import Claim, ClaimSummary, Customer, Handler, Policy
from backend.seed import ensure_seeded

INSTRUCTIONS = Path(__file__).parent / "instructions.md"

app = FastAPI(title="UnderCover")


def database() -> Iterator[sqlite3.Connection]:
    """Open the database for one request, seeding it on first use."""
    conn = db.connect()
    ensure_seeded(conn)
    try:
        yield conn
    finally:
        conn.close()


Db = Annotated[sqlite3.Connection, Depends(database)]


def find(conn: sqlite3.Connection, sql: str, key: str, label: str) -> sqlite3.Row:
    """Return the one row the query finds for the key, or raise a 404."""
    row = conn.execute(sql, (key,)).fetchone()
    if row is None:
        raise HTTPException(404, f"{label} {key} not found")
    return row


def setting(conn: sqlite3.Connection, name: str) -> str:
    """Return one stored setting."""
    return conn.execute(
        "SELECT value FROM settings WHERE name = ?", (name,)
    ).fetchone()[0]


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(conn: Db) -> list[ClaimSummary]:
    """List the claims queue with the state of each claim."""
    rows = conn.execute(
        "SELECT claims.data, claims.status, customers.data AS customer FROM claims"
        " JOIN customers USING (customer_id) ORDER BY claim_id"
    ).fetchall()
    return [
        ClaimSummary.model_validate(
            json.loads(row["data"])
            | {
                "status": row["status"],
                "customer_name": json.loads(row["customer"])["name"],
            }
        )
        for row in rows
    ]


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, conn: Db) -> Claim:
    """Get one claim in full: the story, the items and the documents."""
    row = find(
        conn,
        "SELECT data, status FROM claims WHERE claim_id = ?",
        claim_id,
        "Claim",
    )
    return Claim.model_validate(json.loads(row["data"]) | {"status": row["status"]})


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
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


@app.get("/api/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str, conn: Db) -> Customer:
    """Get one customer with their claim history."""
    row = find(
        conn,
        "SELECT data FROM customers WHERE customer_id = ?",
        customer_id,
        "Customer",
    )
    return Customer.model_validate_json(row["data"])


@app.get(
    "/api/policy-wording",
    operation_id="get_policy_wording",
    response_class=PlainTextResponse,
)
def get_policy_wording(conn: Db) -> str:
    """Get the policy wording as Markdown."""
    return setting(conn, "policy_wording")


@app.get(
    "/api/instructions",
    operation_id="get_instructions",
    response_class=PlainTextResponse,
)
def get_instructions() -> str:
    """Get the UnderCover Agent's instructions as Markdown."""
    return INSTRUCTIONS.read_text(encoding="utf-8")


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers(conn: Db) -> list[Handler]:
    """List the claims handlers."""
    rows = conn.execute("SELECT data FROM handlers ORDER BY handler_id").fetchall()
    return [Handler.model_validate_json(row["data"]) for row in rows]
