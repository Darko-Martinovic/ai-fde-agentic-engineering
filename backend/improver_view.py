"""What the improver reads of a round's results, as the lab's `read_results`
gives it: the current version and its scores on both sets; from its latest
round evaluation of the evaluation set, the claims it got wrong and the five
right ones it explained least well, beside the handlers' decisions with their
reasons; the earlier rounds; what the round works to; what's left of its
spending limit; and the models allowed. From the held-out set, scores only."""

import json
from typing import Any

from sqlalchemy import Connection

from backend import spending
from backend.evaluation_views import load_evaluation
from backend.improver_models import (
    Answer,
    BesideHandler,
    CurrentVersion,
    EarlierRound,
    HandlersAnswer,
    ImproverView,
    JudgesGrade,
    Mistakes,
)
from backend.run_models import EvaluationClaim
from backend.store import claims, evaluations, platform_settings, rounds, runs, versions
from backend.verdict import RULE
from backend.version_models import ModelAllowed
from backend.version_scores import version_scores

EVALUATION_SET = "evaluation"
# The right decisions the improver sees, those the judge graded lowest
EXPLAINED_LEAST_WELL = 5


def beside_handler(
    conn: Connection, copy: EvaluationClaim, reasons: dict[str, dict[str, str]]
) -> BesideHandler:
    """A copy's answer beside the handler's on the claim it copies."""
    original = claims.claim(conn, copy.copy_of)
    summary = json.loads(original["data"])["summary"] if original else ""
    return BesideHandler(
        claim_id=copy.copy_of,
        summary=summary,
        agent=Answer(decision=copy.decision, payout=copy.payout, reasons=copy.reasons),
        handler=HandlersAnswer(
            decision=copy.handler_decision,
            payout=copy.handler_payout,
            reason=reasons[copy.copy_of]["reason"],
            reference=reasons[copy.copy_of]["reference"],
        ),
        judge=JudgesGrade.model_validate(copy.model_dump()),
    )


def mistakes(conn: Connection, version: int) -> Mistakes:
    """A version's mistakes in its latest round evaluation of the evaluation
    set, or none before its first."""
    scored = [
        run["run_id"]
        for run in runs.scored_on(conn, version)
        if run["evaluation_set"] == EVALUATION_SET
    ]
    if not scored:
        return Mistakes(wrong=[], explained_least_well=[])
    copies = load_evaluation(conn, scored[-1]).claims
    reasons = evaluations.handlers_reasons(conn, EVALUATION_SET)
    right = [c for c in copies if c.right]
    weakest = sorted(right, key=lambda c: (c.grade is None, c.grade or 0))
    return Mistakes(
        wrong=[beside_handler(conn, c, reasons) for c in copies if not c.right],
        explained_least_well=[
            beside_handler(conn, c, reasons) for c in weakest[:EXPLAINED_LEAST_WELL]
        ],
    )


def earlier_rounds(conn: Connection, round_id: int) -> list[EarlierRound]:
    """The rounds before this one, oldest first, each with the version it
    tried and the verdict on it."""
    found = []
    for row in reversed(rounds.every(conn)):
        if row["round_id"] >= round_id:
            continue
        tried = versions.version(conn, row["version_tried"] or 0)
        found.append(
            EarlierRound.model_validate(
                row
                | {
                    "model": tried["model"] if tried else None,
                    "reasoning_effort": tried["reasoning_effort"] if tried else None,
                    "reason": tried["reason"] if tried else None,
                    "held_out_before": row["scores_before"],
                    "held_out_after": row["scores_after"],
                }
            )
        )
    return found


def improver_view(conn: Connection, row: dict[str, Any]) -> ImproverView:
    """What the improver reads in a round, as it stands."""
    round_id = row["round_id"]
    current = versions.current(conn)
    version = versions.version(conn, current)
    settings = platform_settings.row(conn, row["settings_number"])
    return ImproverView(
        current_version=CurrentVersion.model_validate(dict(version or {})),
        scores=version_scores(conn, current),
        evaluation_set=mistakes(conn, current),
        earlier_rounds=earlier_rounds(conn, round_id),
        objectives_on_the_held_out_set=settings["objectives"],
        noise=settings["noise"],
        tolerance=settings["tolerance"],
        rule=RULE,
        spending_left=round(
            settings["spending_limit"] - spending.spent(conn, round_id), 4
        ),
        models_allowed=[ModelAllowed(**m) for m in platform_settings.models(conn)],
    )
