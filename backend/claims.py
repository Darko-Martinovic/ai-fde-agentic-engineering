"""The claims queue and each claim, as recorded."""

import json

from fastapi import APIRouter

from backend.api import Db, load_claim
from backend.models import Claim, ClaimSummary
from backend.store import claims

router = APIRouter(prefix="/api/claims")


@router.get("", operation_id="list_claims")
def list_claims(conn: Db) -> list[ClaimSummary]:
    """List the claims queue with the state, latest decision and payment of each."""
    return [
        ClaimSummary.model_validate(
            json.loads(row["data"])
            | {
                "status": row["status"],
                "customer_name": json.loads(row["customer"])["name"],
                "decision": row["decision"],
                "payout": row["payout"],
                "paid": row["paid"],
            }
        )
        for row in claims.queue(conn)
    ]


@router.get("/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, conn: Db) -> Claim:
    """Get one claim in full: the story, the items, the documents and the decisions."""
    return load_claim(conn, claim_id)
