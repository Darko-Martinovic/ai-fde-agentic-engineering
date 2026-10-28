"""A round of improvement's work in the agent's service: the first evaluations
the version it starts from still needs, then the improver's stretches of work
between a handler's reviews, and the round's finish. Each stretch ends when the
improver pauses for a handler, when the service records its proposal, or when
it ends, when the round finishes. Work that fails stops the round, with the
error as the reason."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command

from agent import improver, improver_api, tracing
from agent.connection import Refused

log = logging.getLogger(__name__)

OPEN = "open"
SPENT_FIRST = "The round spent its limit in its first evaluations"


@dataclass(frozen=True)
class RoundWorkers:
    """What the service hands a round: the improver's model, built from what
    the round gives of it, a saver for the improver's progress, and how to work
    one of the round's evaluations through the dispatcher."""

    model_for: Callable[[dict[str, Any]], BaseChatModel]
    new_saver: Callable[[], BaseCheckpointSaver[Any]]
    evaluate: Callable[[dict[str, Any]], None]


def is_open(round_id: int) -> bool:
    return improver_api.get_round(round_id)["status"] == OPEN


def first_evaluations(worked: dict[str, Any], workers: RoundWorkers) -> bool:
    """Run the evaluations the version a round starts from still needs, checking
    the round after each, and stop the round when they spend its limit; return
    whether it's still open."""
    round_id = worked["round_id"]
    for evaluation_set in worked["first_evaluations"]:
        workers.evaluate(improver_api.create_round_evaluation(round_id, evaluation_set))
        now = improver_api.get_round(round_id)
        if now["status"] != OPEN:
            return False
        if now["spent"] >= now["spending_limit"]:
            improver_api.finish_round(round_id, True, SPENT_FIRST)
            return False
    return True


def record(round_id: int, request: dict[str, Any]) -> None:
    """Record the proposal the improver waits on, for a handler's review."""
    if request["name"] == "propose_change":
        improver_api.record_change_proposal(round_id, request["args"])
    else:
        improver_api.record_recipe_proposal(round_id, request["args"])


def stretch(round_id: int, workers: RoundWorkers, start: Command[Any] | None) -> None:
    """Run the improver from `start` until it pauses for a handler, recording
    its proposal, or ends, finishing the round if it's still open. A proposal
    the backend refuses goes back to the improver as a rejection with the
    reason, and it carries on."""
    worked = improver_api.get_round(round_id)
    agent = improver.improver(
        workers.model_for(worked["improver"]),
        worked["instructions"],
        workers.new_saver(),
    )
    context = improver.RoundContext(
        round_id=round_id,
        model=worked["improver"]["model"],
        provider=worked["improver"]["provider"],
        models_allowed=worked["models_allowed"],
        evaluate=workers.evaluate,
    )
    while True:
        waiting = tracing.round_trace(
            round_id,
            worked["thread_id"],
            lambda config, start=start: improver.work_stretch(
                agent, context, worked["thread_id"], start, config
            ),
        )
        if waiting is None:
            break
        try:
            record(round_id, waiting)
            return
        except Refused as refused:
            start = improver.resume(False, f"Refused: {refused.detail}")
    if is_open(round_id):
        improver_api.finish_round(round_id, False, "")


def safely(round_id: int, work: Callable[[], object]) -> None:
    """Do a round's work, stopping the round with the error as the reason when
    it fails."""
    try:
        work()
    except Exception as error:
        log.exception("Round %s stopped", round_id)
        try:
            if is_open(round_id):
                reason = f"{type(error).__name__}: {error}"
                improver_api.finish_round(round_id, True, reason)
        except Exception:  # noqa: BLE001 - the round's own error is logged above
            log.exception("Round %s couldn't be stopped", round_id)


def work_round(worked: dict[str, Any], workers: RoundWorkers) -> None:
    """Work a round from its start: its first evaluations, then the improver
    until it pauses for a handler or ends."""
    round_id = worked["round_id"]
    safely(
        round_id,
        lambda: first_evaluations(worked, workers) and stretch(round_id, workers, None),
    )


def resume_round(
    round_id: int, approved: bool, note: str, workers: RoundWorkers
) -> None:
    """Carry a round on past a handler's review, which the service recorded."""
    safely(
        round_id, lambda: stretch(round_id, workers, improver.resume(approved, note))
    )
