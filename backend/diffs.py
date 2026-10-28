"""The lines that differ between two texts, as the lab's `show_changed_lines`
finds them with difflib, for the dashboard's diff of a version or a recipe:
each changed stretch with two lines around it."""

import difflib

from backend.version_models import DiffKind, DiffLine, Hunk

CONTEXT_LINES = 2
HEADERS = ("---", "+++")
KINDS: dict[str, DiffKind] = {"+": "added", "-": "removed", " ": "context"}


def changes(old: str, new: str) -> list[Hunk]:
    """The changed stretches of `new` against `old`, each with its lines marked
    added, removed or context. The same text has none."""
    hunks: list[Hunk] = []
    lines = difflib.unified_diff(
        old.splitlines(), new.splitlines(), lineterm="", n=CONTEXT_LINES
    )
    for line in lines:
        if line.startswith(HEADERS):
            continue
        if line.startswith("@@"):
            hunks.append(Hunk(heading=line, lines=[]))
        else:
            hunks[-1].lines.append(DiffLine(kind=KINDS[line[0]], text=line[1:]))
    return hunks


def counted(hunks: list[Hunk], kind: DiffKind) -> int:
    """How many lines of a kind the changes hold."""
    return sum(line.kind == kind for hunk in hunks for line in hunk.lines)
