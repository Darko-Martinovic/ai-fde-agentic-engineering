"""The rules a round keeps, which the backend enforces whoever asks: one round
open at a time, a change only to a model allowed, one proposal waiting at a
time and a review only of that one, by a handler who can sign off payouts over
the limit, the verdict on the version it tried by the business's rule, and a
version under test rolled back when the round ends before its verdict."""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import Connection

from backend.api import found, now
from backend.claim_rules import approval_limit
from backend.models import Handler
from backend.round_models import Proposal, ProposalKind, RoundStatus, Verdict
from backend.round_views import waiting
from backend.signed_in import refuse_unless_senior
from backend.store import platform_settings, records, rounds, runs, versions
from backend.verdict import keep_or_roll_back
from backend.version_models import Verdict as VersionVerdict
from backend.version_scores import NEEDED, version_scores

REVIEW = "review the improver's proposals"
COULDNT_AFFORD = "the round couldn't afford to evaluate it"
STOPPED_BEFORE_VERDICT = "the round was stopped before its verdict"
NEVER_EVALUATED = "the round ended before it was evaluated"


def refuse_while_open(conn: Connection) -> None:
    """Refuse a new round while one is open."""
    for round_id in rounds.open_ones(conn):
        raise HTTPException(409, f"Round {round_id} is still open")


def not_allowed(model: str, reasoning_effort: str) -> str:
    return (
        f"{model} at {reasoning_effort} isn't allowed. Choose from the models allowed."
    )


def refuse_unless_allowed(conn: Connection, model: str, reasoning_effort: str) -> None:
    """Refuse a change to a model, or a reasoning effort, not allowed."""
    allowed = platform_settings.model(conn, model)
    if allowed is None or reasoning_effort not in allowed["reasoning_efforts"]:
        raise HTTPException(422, not_allowed(model, reasoning_effort))


def refuse_while_waiting(conn: Connection, round_id: int) -> None:
    """Refuse a proposal while another waits for a handler's review."""
    pending = waiting(conn, round_id)
    if pending:
        raise HTTPException(
            409, f"Proposal {pending.proposal_id} is waiting for a handler's review"
        )


def waiting_proposal(conn: Connection, round_id: int, proposal_id: int) -> Proposal:
    """The round's proposal waiting for a review, which must be the one named:
    a 404 for another round's or none, a 409 for one not waiting."""
    proposed = {p["proposal_id"] for p in rounds.round_proposals(conn, round_id)}
    if proposal_id not in proposed:
        raise HTTPException(
            404, f"Proposal {proposal_id} not found in round {round_id}"
        )
    pending = waiting(conn, round_id)
    if pending is None or pending.proposal_id != proposal_id:
        raise HTTPException(409, f"Proposal {proposal_id} isn't waiting for a review")
    return pending


def senior_handler(conn: Connection, handler_id: str, action: str = REVIEW) -> Handler:
    """The handler taking an action in a round, who must be able to sign off
    payouts over the limit."""
    record = found(records.handler(conn, handler_id), "Handler", handler_id)
    handler = Handler.model_validate_json(record)
    refuse_unless_senior(handler, action, approval_limit(conn))
    return handler


def approved(conn: Connection, round_id: int, kind: ProposalKind) -> dict[str, Any]:
    """The round's latest proposal of a kind, which a handler must have approved."""
    latest = [p for p in rounds.round_proposals(conn, round_id) if p["kind"] == kind]
    if not latest or latest[-1]["review"] != "approved":
        raise HTTPException(409, f"Round {round_id} has no approved {kind}")
    return latest[-1]


def evaluated(conn: Connection, row: dict[str, Any]) -> str | None:
    """Why the version a round tried can't be judged on its evaluations, if it
    can't: it had none, as when the round couldn't afford them, or they were
    stopped or not all finished."""
    tried = [
        run
        for run in runs.of_round(conn, row["round_id"])
        if run["version"] == row["version_tried"]
    ]
    if not tried:
        return COULDNT_AFFORD
    for run in tried:
        if run["status"] == "running":
            raise HTTPException(409, f"Run {run['run_id']} is still running")
    if any(run["status"] == "stopped" for run in tried):
        return "its evaluations were stopped"
    done = [run["evaluation_set"] for run in tried]
    if any(done.count(name) < needed for name, needed in NEEDED.items()):
        return "its evaluations weren't all run"
    return None


def decide(conn: Connection, row: dict[str, Any]) -> None:
    """Keep or roll back the version a round tried, by the rule in the round's
    settings, from its held-out scores in the round beside the current
    version's, and record the verdict on the version and the round."""
    before = version_scores(conn, row["version_before"])["held_out"]
    after = version_scores(conn, row["version_tried"], row["round_id"])["held_out"]
    why = evaluated(conn, row)
    kept = False
    if why is None and (before is None or after is None):
        why = "the current version has no held-out scores"
    if why is None and before and after:
        settings = platform_settings.row(conn, row["settings_number"])
        kept, why = keep_or_roll_back(after, before, settings)
    verdict = VersionVerdict.KEPT if kept else VersionVerdict.ROLLED_BACK
    versions.decide(conn, row["version_tried"], verdict, str(why), now())
    rounds.change(
        conn,
        row["round_id"],
        {
            "verdict": verdict,
            "verdict_reason": why,
            "scores_before": before.model_dump() if before else None,
            "scores_after": after.model_dump() if after else None,
        },
    )


def verdict_of(conn: Connection, row: dict[str, Any]) -> Verdict:
    """The verdict a round recorded on the version it tried."""
    scores = version_scores(conn, row["version_tried"], row["round_id"])
    return Verdict(
        version=row["version_tried"],
        kept=row["verdict"] == VersionVerdict.KEPT,
        why=row["verdict_reason"],
        current_version=versions.current(conn),
        held_out_before=row["scores_before"],
        held_out_after=row["scores_after"],
        evaluation_after=scores["evaluation"],
    )


def end(
    conn: Connection,
    row: dict[str, Any],
    status: RoundStatus,
    reason: str | None,
    stopped_by: str | None = None,
) -> None:
    """End an open round, finished or stopped, rolling back a version under
    test that has no verdict."""
    if row["version_tried"] is not None and row["verdict"] is None:
        why = (
            STOPPED_BEFORE_VERDICT if status == RoundStatus.STOPPED else NEVER_EVALUATED
        )
        versions.decide(
            conn, row["version_tried"], VersionVerdict.ROLLED_BACK, why, now()
        )
        rounds.change(
            conn,
            row["round_id"],
            {"verdict": VersionVerdict.ROLLED_BACK, "verdict_reason": why},
        )
    rounds.change(
        conn,
        row["round_id"],
        {
            "status": status,
            "stop_reason": reason,
            "stopped_by": stopped_by,
            "finished_at": now(),
        },
    )
