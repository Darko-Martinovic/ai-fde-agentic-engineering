"""The judge, Jev, which grades the agent's explanation of a claim against the
handler's reason and reference, as labs/week2day5.ipynb does: through
OpenRouter's Decisions endpoint, in alpha, with the openrouter package. The
only module that calls the judge or knows its address, JUDGE_URL. It runs in
the backend, which holds the handlers' decisions, so their reasons never
leave it."""

import logging
from dataclasses import dataclass
from functools import cache
from typing import Any

from openrouter import OpenRouter
from openrouter.utils import BackoffStrategy, RetryConfig

from settings import setting

log = logging.getLogger(__name__)

JEV = "typesafe/jev-1.13"
# Jev numbers the grades by their position in the list, so F is 0 and A is 3
RUBRIC = {
    "F": (
        "different grounds from the handler's reason, or it contradicts the"
        " handler's reason"
    ),
    "C": (
        "partly the same as the handler's reason: one of the handler's grounds or"
        " the section is missing, or it adds a ground the handler did not give"
    ),
    "B": (
        "the same grounds and the same section of the policy wording as the"
        " handler's reason"
    ),
    "A": (
        "the same grounds and section as the handler's reason, and clearly better"
        " expressed: clearer for the customer, with the section and the figures,"
        " shorter, and no jargon"
    ),
}
GRADES = list(RUBRIC)
QUESTIONS = {
    "grade": {
        "type": "score",
        "instructions": (
            "An expert claims handler decided a travel insurance claim and gave"
            " `handler.reason`, resting on `handler.reference`. Grade how well"
            " `agent.reason` explains the same decision."
        ),
        "criteria": [f"{letter}: {text}" for letter, text in RUBRIC.items()],
    },
    "same_grounds": {
        "type": "noul",
        "instructions": (
            "`agent.reason` gives the same main grounds for the decision as"
            " `handler.reason`"
        ),
    },
    "same_section": {
        "type": "noul",
        "instructions": (
            "`agent.section` is the same section of the policy wording as"
            " `handler.reference`"
        ),
    },
}
# A grading call that takes longer is left ungraded, so finishing an evaluation
# stays well within the agent's wait for the backend
TIMEOUT_MS = 10_000
# The SDK's retries are off: a claim the judge can't grade is left ungraded
NO_RETRIES = RetryConfig("none", BackoffStrategy(0, 0, 1, 0), False)


@dataclass(frozen=True)
class Grade:
    """Jev's grade: its score from 0 (F) to 3 (A), its most likely level as a
    letter, never the score rounded, the probability of each check, and what
    the call cost."""

    score: float
    letter: str
    same_grounds: float
    same_section: float
    cost: float


# An undecided claim is graded F without asking the judge
UNDECIDED = Grade(score=0.0, letter=GRADES[0], same_grounds=0, same_section=0, cost=0)


@cache
def client() -> OpenRouter:
    return OpenRouter(api_key=setting("OPENROUTER_API_KEY"))


def ask(state: dict[str, Any]) -> Grade:
    """Ask Jev the three questions about one claim."""
    response = client().alpha.decisions.create(
        model=JEV,
        state=state,
        questions=QUESTIONS,
        server_url=setting("JUDGE_URL"),
        timeout_ms=TIMEOUT_MS,
        retries=NO_RETRIES,
    )
    answers: dict[str, Any] = response.answers
    probabilities: dict[str, float] = answers["grade"].probabilities
    most_likely = max(probabilities, key=lambda level: probabilities[level])
    return Grade(
        score=answers["grade"].score,
        letter=GRADES[int(most_likely)],
        same_grounds=answers["same_grounds"].noul,
        same_section=answers["same_section"].noul,
        cost=response.usage.cost or 0.0,
    )


def grade(handler: dict[str, Any], agent: dict[str, Any]) -> Grade | None:
    """Grade the agent's decision, reason and section against the handler's
    decision, reason and reference, or None when the judge can't: any error,
    a timeout or an answer without the grade, which is logged."""
    try:
        return ask({"handler": handler, "agent": agent})
    except Exception:  # noqa: BLE001 - an ungraded claim never stops a finish
        log.warning("The judge didn't grade a claim", exc_info=True)
        return None
