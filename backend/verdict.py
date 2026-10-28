"""The business's rule for keeping a new version or rolling it back, as the
lab's `compare` and `keep_or_roll_back`: from its held-out scores beside the
current version's, and the round's settings. Accuracy and the grade compare as
differences, cost and time per claim as fractions of the old value."""

from typing import Any

from backend.round_models import Scores

DIFFERENCES = ("accuracy", "grade")
FRACTIONS = ("cost_per_claim", "seconds_per_claim")
RULE = (
    "A new version is kept when it meets the objectives, at least one score"
    " improves by more than the noise and none gets worse by more than the"
    " tolerance"
)


def compare(new: Scores, old: Scores, settings: dict[str, Any]) -> tuple[list, list]:
    """Which scores got better by more than the noise, and which got worse by
    more than the tolerance."""
    noise, tolerance = settings["noise"], settings["tolerance"]
    newer, older = new.model_dump(), old.model_dump()
    better, worse = [], []
    for name in DIFFERENCES:
        if newer[name] > older[name] + noise[name]:
            better.append(name)
        if newer[name] < older[name] - tolerance[name]:
            worse.append(name)
    for name in FRACTIONS:
        if newer[name] < older[name] * (1 - noise[name]):
            better.append(name)
        if newer[name] > older[name] * (1 + tolerance[name]):
            worse.append(name)
    return better, worse


def keep_or_roll_back(
    new: Scores, old: Scores, settings: dict[str, Any]
) -> tuple[bool, str]:
    """Keep the new version or roll it back, and why. A version without a
    grade is rolled back; so is one beside a current version without one."""
    if new.grade is None:
        return False, "it has no grade"
    if old.grade is None:
        old = old.model_copy(update={"grade": 0.0})
    missed = [
        name
        for name, floor in settings["objectives"].items()
        if getattr(new, name) < floor
    ]
    better, worse = compare(new, old, settings)
    if missed:
        return False, f"it missed the objectives on {', '.join(missed)}"
    if worse:
        return False, f"{', '.join(worse)} got worse"
    if not better:
        return False, "no score improved by more than the noise"
    return True, f"{', '.join(better)} improved"
