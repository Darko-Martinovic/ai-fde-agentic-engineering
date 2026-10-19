"""What the agent's work on the queue adds up to, for the Insights page."""

import json
import sqlite3
from collections import Counter, defaultdict, deque
from datetime import datetime
from statistics import median

from fastapi import APIRouter
from pydantic import BaseModel

from backend.api import Db
from backend.models import ClaimStatus, DecisionKind
from backend.workflow import approval_limit

router = APIRouter(prefix="/api/insights")

REFUSED = "Refused ("


class Totals(BaseModel):
    claims: int
    decided: int
    straight_through: int
    sign_offs: int
    referred: int
    waiting_for_handler: int
    tool_calls: int
    refused: int
    median_seconds: float | None
    longest_seconds: float | None
    claimed: float
    approved: float
    paid: float
    held: float


class TypeMix(BaseModel):
    claim_type: str
    approve: int
    decline: int
    refer: int


class ToolUse(BaseModel):
    tool: str
    calls: int
    refused: int


class SectionCount(BaseModel):
    section: str
    claims: int


class ClaimWork(BaseModel):
    claim_id: str
    claim_type: str
    status: ClaimStatus
    decision: DecisionKind | None
    started_at: datetime
    finished_at: datetime
    seconds: float
    tool_calls: int
    refused: int


class Insights(BaseModel):
    totals: Totals
    by_type: list[TypeMix]
    tools: list[ToolUse]
    sections: list[SectionCount]
    claims: list[ClaimWork]


def latest_runs(conn: sqlite3.Connection) -> dict[str, list[sqlite3.Row]]:
    """Return the steps of each claim's latest run, in order."""
    runs: dict[str, dict[str, list[sqlite3.Row]]] = defaultdict(dict)
    for step in conn.execute(
        "SELECT claim_id, thread_id, kind, text, recorded_at FROM steps"
        " ORDER BY step_id"
    ):
        runs[step["claim_id"]].setdefault(step["thread_id"], []).append(step)
    return {claim_id: list(threads.values())[-1] for claim_id, threads in runs.items()}


def tool_calls(steps: list[sqlite3.Row]) -> list[tuple[str, bool]]:
    """Pair each tool call with its result: the tool and whether it was refused."""
    pending: deque[str] = deque()
    calls: list[tuple[str, bool]] = []
    for step in steps:
        if step["kind"] == "tool_call":
            pending.append(step["text"].split(" ", 1)[0])
        elif step["kind"] == "tool_result":
            calls.append((pending.popleft(), step["text"].startswith(REFUSED)))
    return calls + [(tool, False) for tool in pending]


def sections(policy_section: str | None) -> list[str]:
    return [s.strip() for s in (policy_section or "").split(";") if s.strip()]


@router.get("", operation_id="get_insights")
def get_insights(conn: Db) -> Insights:
    """Sum up the agent's work on the queue: outcomes, time, tools and money."""
    claims = {
        row["claim_id"]: json.loads(row["data"]) | {"status": row["status"]}
        for row in conn.execute("SELECT claim_id, status, data FROM claims")
    }
    decisions = {
        row["claim_id"]: row
        for row in conn.execute(
            "SELECT claim_id, decision, payout, policy_section FROM decisions"
            " WHERE decided_by = 'agent'"
        )
    }
    payments = {
        row["claim_id"]: row
        for row in conn.execute("SELECT claim_id, amount, authorized_by FROM payments")
    }
    limit = approval_limit(conn)

    def straight_through(claim_id: str) -> bool:
        payment = payments.get(claim_id)
        if decisions[claim_id]["decision"] == "decline":
            return True
        return payment is not None and payment["authorized_by"] == "agent"

    approvals = [d for d in decisions.values() if d["decision"] == "approve"]
    mix: dict[str, Counter[str]] = defaultdict(Counter)
    cited: Counter[str] = Counter()
    for claim_id, decision in decisions.items():
        mix[claims[claim_id]["claim_type"]][decision["decision"]] += 1
        cited.update(sections(decision["policy_section"]))

    work: list[ClaimWork] = []
    used: dict[str, Counter[bool]] = defaultdict(Counter)
    for claim_id, steps in latest_runs(conn).items():
        calls = tool_calls(steps)
        for tool, refused in calls:
            used[tool][refused] += 1
        started = datetime.fromisoformat(steps[0]["recorded_at"])
        finished = datetime.fromisoformat(steps[-1]["recorded_at"])
        decision = decisions.get(claim_id)
        work.append(
            ClaimWork(
                claim_id=claim_id,
                claim_type=claims[claim_id]["claim_type"],
                status=claims[claim_id]["status"],
                decision=decision["decision"] if decision else None,
                started_at=started,
                finished_at=finished,
                seconds=(finished - started).total_seconds(),
                tool_calls=len(calls),
                refused=sum(refused for _, refused in calls),
            )
        )

    seconds = [w.seconds for w in work]
    totals = Totals(
        claims=len(claims),
        decided=len(decisions),
        straight_through=sum(straight_through(c) for c in decisions),
        sign_offs=sum(d["payout"] > limit for d in approvals),
        referred=sum(d["decision"] == "refer" for d in decisions.values()),
        waiting_for_handler=sum(
            c["status"] in ("awaiting_sign_off", "referred") for c in claims.values()
        ),
        tool_calls=sum(w.tool_calls for w in work),
        refused=sum(w.refused for w in work),
        median_seconds=median(seconds) if seconds else None,
        longest_seconds=max(seconds) if seconds else None,
        claimed=sum(claims[c]["amount_claimed"] for c in decisions),
        approved=sum(d["payout"] for d in approvals),
        paid=sum(p["amount"] for p in payments.values()),
        held=sum(
            decisions[c]["payout"]
            for c, claim in claims.items()
            if claim["status"] == "awaiting_sign_off"
        ),
    )
    return Insights(
        totals=totals,
        by_type=[
            TypeMix(
                claim_type=claim_type,
                approve=counts["approve"],
                decline=counts["decline"],
                refer=counts["refer"],
            )
            for claim_type, counts in sorted(mix.items())
        ],
        tools=[
            ToolUse(tool=tool, calls=counts.total(), refused=counts[True])
            for tool, counts in sorted(used.items(), key=lambda t: -t[1].total())
        ],
        sections=[
            SectionCount(section=section, claims=count)
            for section, count in cited.most_common()
        ],
        claims=sorted(work, key=lambda w: w.started_at),
    )
