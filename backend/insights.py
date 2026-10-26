"""What the agent's work on the queue adds up to, for the Insights page."""

import json
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import Connection, RowMapping

from backend.api import Db
from backend.claim_rules import approval_limit
from backend.models import FOR_A_HANDLER, ClaimStatus, DecisionKind
from backend.store import claims, steps

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


@dataclass(frozen=True)
class Records:
    """The records Insights adds up, each keyed by claim."""

    claims: dict[str, dict[str, Any]]
    decisions: dict[str, RowMapping]
    payments: dict[str, RowMapping]
    limit: float

    @classmethod
    def load(cls, conn: Connection) -> "Records":
        return cls(
            claims={
                row["claim_id"]: json.loads(row["data"]) | {"status": row["status"]}
                for row in claims.every_claim(conn)
            },
            decisions={row["claim_id"]: row for row in claims.agent_decisions(conn)},
            payments={row["claim_id"]: row for row in claims.payments(conn)},
            limit=approval_limit(conn),
        )

    def straight_through(self, claim_id: str) -> bool:
        """Declined, or approved and paid by the agent, with no handler."""
        payment = self.payments.get(claim_id)
        if self.decisions[claim_id]["decision"] == "decline":
            return True
        return payment is not None and payment["authorized_by"] == "agent"

    def approvals(self) -> list[RowMapping]:
        return [d for d in self.decisions.values() if d["decision"] == "approve"]


def latest_runs(conn: Connection) -> dict[str, list[RowMapping]]:
    """Return the steps of each claim's latest run, in order."""
    runs: dict[str, dict[str, list[RowMapping]]] = defaultdict(dict)
    for step in steps.every_step(conn):
        runs[step["claim_id"]].setdefault(step["thread_id"], []).append(step)
    return {claim_id: list(threads.values())[-1] for claim_id, threads in runs.items()}


def tool_calls(run: list[RowMapping]) -> list[tuple[str, bool]]:
    """Pair each tool call with its result: the tool and whether it was refused."""
    pending: deque[str] = deque()
    calls: list[tuple[str, bool]] = []
    for step in run:
        if step["kind"] == "tool_call":
            pending.append(step["text"].split(" ", 1)[0])
        elif step["kind"] == "tool_result":
            calls.append((pending.popleft(), step["text"].startswith(REFUSED)))
    return calls + [(tool, False) for tool in pending]


def sections(policy_section: str | None) -> list[str]:
    return [s.strip() for s in (policy_section or "").split(";") if s.strip()]


def claim_work(records: Records, claim_id: str, run: list[RowMapping]) -> ClaimWork:
    """One claim's latest run: its time, its tool calls and its outcome."""
    calls = tool_calls(run)
    started = datetime.fromisoformat(run[0]["recorded_at"])
    finished = datetime.fromisoformat(run[-1]["recorded_at"])
    decision = records.decisions.get(claim_id)
    return ClaimWork(
        claim_id=claim_id,
        claim_type=records.claims[claim_id]["claim_type"],
        status=records.claims[claim_id]["status"],
        decision=decision["decision"] if decision else None,
        started_at=started,
        finished_at=finished,
        seconds=(finished - started).total_seconds(),
        tool_calls=len(calls),
        refused=sum(refused for _, refused in calls),
    )


def tool_use(runs: dict[str, list[RowMapping]]) -> list[ToolUse]:
    """Each tool's calls and refusals, the most called first."""
    used: dict[str, Counter[bool]] = defaultdict(Counter)
    for run in runs.values():
        for tool, refused in tool_calls(run):
            used[tool][refused] += 1
    return [
        ToolUse(tool=tool, calls=counts.total(), refused=counts[True])
        for tool, counts in sorted(used.items(), key=lambda t: -t[1].total())
    ]


def type_mix(records: Records) -> list[TypeMix]:
    """The agent's decisions on each claim type."""
    mix: dict[str, Counter[str]] = defaultdict(Counter)
    for claim_id, decision in records.decisions.items():
        mix[records.claims[claim_id]["claim_type"]][decision["decision"]] += 1
    return [
        TypeMix(
            claim_type=claim_type,
            approve=counts["approve"],
            decline=counts["decline"],
            refer=counts["refer"],
        )
        for claim_type, counts in sorted(mix.items())
    ]


def sections_cited(records: Records) -> list[SectionCount]:
    cited: Counter[str] = Counter()
    for decision in records.decisions.values():
        cited.update(sections(decision["policy_section"]))
    return [SectionCount(section=s, claims=n) for s, n in cited.most_common()]


def totals(records: Records, work: list[ClaimWork]) -> Totals:
    """The figures across the queue: outcomes, calls, time and money."""
    seconds = [w.seconds for w in work]
    decided = records.decisions
    in_state = Counter(c["status"] for c in records.claims.values())
    return Totals(
        claims=len(records.claims),
        decided=len(decided),
        straight_through=sum(records.straight_through(c) for c in decided),
        sign_offs=sum(d["payout"] > records.limit for d in records.approvals()),
        referred=sum(d["decision"] == "refer" for d in decided.values()),
        waiting_for_handler=sum(
            in_state[s] for s in ("awaiting_sign_off", *FOR_A_HANDLER)
        ),
        tool_calls=sum(w.tool_calls for w in work),
        refused=sum(w.refused for w in work),
        median_seconds=median(seconds) if seconds else None,
        longest_seconds=max(seconds) if seconds else None,
        claimed=sum(records.claims[c]["amount_claimed"] for c in decided),
        approved=sum(d["payout"] for d in records.approvals()),
        paid=sum(p["amount"] for p in records.payments.values()),
        held=sum(
            decided[c]["payout"]
            for c, claim in records.claims.items()
            if claim["status"] == "awaiting_sign_off"
        ),
    )


@router.get("", operation_id="get_insights")
def get_insights(conn: Db) -> Insights:
    """Sum up the agent's work on the queue: outcomes, time, tools and money."""
    records = Records.load(conn)
    runs = latest_runs(conn)
    work = [claim_work(records, claim_id, run) for claim_id, run in runs.items()]
    return Insights(
        totals=totals(records, work),
        by_type=type_mix(records),
        tools=tool_use(runs),
        sections=sections_cited(records),
        claims=sorted(work, key=lambda w: w.started_at),
    )
