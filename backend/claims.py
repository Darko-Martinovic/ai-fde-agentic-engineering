"""The claims queue and each claim, as recorded."""

import json

from fastapi import APIRouter

from backend.api import Db, load_claim
from backend.models import Claim, ClaimSummary

router = APIRouter(prefix="/api/claims")

LIST_CLAIMS = """
WITH latest AS (
    SELECT claim_id, decision, payout FROM decisions
    WHERE decision_id IN (SELECT MAX(decision_id) FROM decisions GROUP BY claim_id)
)
SELECT claims.data, claims.status, customers.data AS customer,
    latest.decision, latest.payout, payments.amount AS paid
FROM claims
JOIN customers USING (customer_id)
LEFT JOIN latest USING (claim_id)
LEFT JOIN payments USING (claim_id)
ORDER BY claim_id
"""


@router.get("", operation_id="list_claims")
def list_claims(conn: Db) -> list[ClaimSummary]:
    """List the claims queue with the state, latest decision and payment of each."""
    rows = conn.execute(LIST_CLAIMS).fetchall()
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
        for row in rows
    ]


@router.get("/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, conn: Db) -> Claim:
    """Get one claim in full: the story, the items, the documents and the decisions."""
    return load_claim(conn, claim_id)
