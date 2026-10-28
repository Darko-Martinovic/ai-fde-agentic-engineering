"""The lines that differ between two texts, as the lab's `show_changed_lines`
finds them with difflib, for the dashboard's diff of a version or a recipe:
each changed stretch with two lines around it."""

import difflib
from itertools import islice
from typing import Literal

from pydantic import BaseModel

CONTEXT_LINES = 2
# unified_diff starts with the two files' names, which a diff of texts has no use for
FILE_HEADERS = 2
DiffKind = Literal["added", "removed", "context"]
KINDS: dict[str, DiffKind] = {"+": "added", "-": "removed", " ": "context"}


class DiffLine(BaseModel):
    kind: DiffKind
    text: str


class Hunk(BaseModel):
    heading: str
    lines: list[DiffLine]


def changes(old: str, new: str) -> list[Hunk]:
    """The changed stretches of `new` against `old`, each with its lines marked
    added, removed or context. The same text has none."""
    hunks: list[Hunk] = []
    lines = difflib.unified_diff(
        old.splitlines(), new.splitlines(), lineterm="", n=CONTEXT_LINES
    )
    for line in islice(lines, FILE_HEADERS, None):
        if line.startswith("@@"):
            hunks.append(Hunk(heading=line, lines=[]))
        else:
            hunks[-1].lines.append(DiffLine(kind=KINDS[line[0]], text=line[1:]))
    return hunks


def counted(hunks: list[Hunk], kind: DiffKind) -> int:
    """How many lines of a kind the changes hold."""
    return sum(line.kind == kind for hunk in hunks for line in hunk.lines)
