"""Versions of the claim agent's configuration made straight in the database,
as a round of improvement would make them, for the tests."""

from datetime import UTC, datetime

from backend import db
from backend.seed import ready
from backend.store import versions
from backend.version_models import Verdict

GEMINI = "google/gemini-3.5-flash-lite"


def add_version(
    instructions: str,
    model: str = GEMINI,
    reasoning_effort: str = "minimal",
    verdict: Verdict | None = Verdict.KEPT,
    based_on: int = 1,
) -> int:
    """Add a version based on another, kept unless told otherwise; return its
    number."""
    now = datetime.now(UTC).isoformat()
    engine = db.engine()
    ready(engine)
    with engine.begin() as conn:
        return versions.add(
            conn,
            {
                "instructions": instructions,
                "model": model,
                "reasoning_effort": reasoning_effort,
                "based_on": based_on,
                "reason": "A test's change.",
                "proposed_by": "Round 1",
                "approved_by": "HND-01",
                "approved_at": now,
                "created_at": now,
                "verdict": verdict,
                "verdict_reason": "accuracy improved" if verdict else None,
                "decided_at": now if verdict else None,
            },
        )
