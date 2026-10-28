"""The documents the agent works from: the policy wording and the claims
manual, which it looks up section by section as a handler would. Its
instructions are in the versions of its configuration."""

import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from backend.api import Db
from backend.models import DocumentName, Section, SectionTitle
from backend.store import records

router = APIRouter(prefix="/api")


# Each document's title, and where it's stored when it's seeded
TITLES: dict[DocumentName, str] = {
    "wording": "Policy wording",
    "manual": "Claims manual",
}
STORED: dict[DocumentName, str] = {
    "wording": "policy_wording",
    "manual": "claims_manual",
}
# The text before a document's first numbered section: its version and scope
OPENING = "Version and scope"
HEADING = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)
WORD = re.compile(r"[a-z0-9]+")
SEARCH_RESULTS = 3
# Words shorter than this, such as "a" and "of", don't count in a search
SHORTEST_WORD = 3
# A word in a section's title counts this much more than one in its text
TITLE_WEIGHT = 2


def sections(conn: Db, document: DocumentName) -> list[Section]:
    """Split a document into its opening (section 0) and its numbered sections.
    A section's text leaves out its heading, which its number and title give."""
    text = records.stored(conn, STORED[document])
    headings = list(HEADING.finditer(text))
    starts = [0] + [heading.end() for heading in headings]
    ends = [heading.start() for heading in headings] + [len(text)]
    names = [(0, OPENING)] + [(int(h[1]), h[2].strip()) for h in headings]
    return [
        Section(
            document=document,
            document_title=TITLES[document],
            number=number,
            title=title,
            text=text[start:end].strip(),
        )
        for (number, title), start, end in zip(names, starts, ends, strict=True)
    ]


def every_section(conn: Db) -> list[Section]:
    return [s for document in STORED for s in sections(conn, document)]


def words(text: str) -> set[str]:
    """The words in a text that carry meaning, lower case, a plural's s dropped."""
    return {
        w.removesuffix("s")
        for w in WORD.findall(text.lower())
        if len(w) >= SHORTEST_WORD
    }


def score(query: set[str], section: Section) -> int:
    """How well a section matches a query; a word in its title counts twice."""
    in_title = len(query & words(section.title))
    return len(query & words(section.text)) + TITLE_WEIGHT * in_title


def title_of(section: Section) -> SectionTitle:
    return SectionTitle(**section.model_dump(exclude={"text"}))


@router.get(
    "/policy-wording",
    operation_id="get_policy_wording",
    response_class=PlainTextResponse,
)
def get_policy_wording(conn: Db) -> str:
    """Get the policy wording as Markdown."""
    return records.stored(conn, STORED["wording"])


@router.get("/documents/sections", operation_id="list_sections")
def list_sections(conn: Db) -> list[SectionTitle]:
    """List the sections of the policy wording and the claims manual, by title."""
    return [title_of(s) for s in every_section(conn)]


@router.get("/documents/search", operation_id="search_documents")
def search_documents(query: str, conn: Db) -> list[SectionTitle]:
    """Find the sections of the wording and the manual that best match a query."""
    wanted = words(query)
    scored = [(score(wanted, s), s) for s in every_section(conn)]
    # A stable sort, so on equal scores the wording comes before the manual
    ranked = sorted((pair for pair in scored if pair[0] > 0), key=lambda p: -p[0])
    return [title_of(s) for _, s in ranked[:SEARCH_RESULTS]]


@router.get("/documents/{document}/sections/{number}", operation_id="read_section")
def read_section(document: DocumentName, number: int, conn: Db) -> Section:
    """Read one section of the policy wording or the claims manual."""
    found = next((s for s in sections(conn, document) if s.number == number), None)
    if found is None:
        raise HTTPException(404, f"There is no section {number} in the {document}")
    return found
