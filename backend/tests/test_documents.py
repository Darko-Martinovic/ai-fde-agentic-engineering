import pytest

from backend.tests.claim_starts import start


def search(client, query):
    response = client.get("/api/documents/search", params={"query": query})
    assert response.status_code == 200
    return [(s["document"], s["number"]) for s in response.json()]


def test_lists_every_section(client):
    sections = client.get("/api/documents/sections").json()
    assert {s["document"] for s in sections} == {"wording", "manual"}
    assert {
        "document": "manual",
        "document_title": "Claims manual",
        "number": 9,
        "title": "Repeat claims",
    } in sections
    # Each document's numbered sections, and its opening as section 0
    assert len([s for s in sections if s["document"] == "manual"]) == 15
    assert len([s for s in sections if s["document"] == "wording"]) == 13


@pytest.mark.parametrize(
    ("query", "first"),
    [
        ("third claim within 12 months", ("manual", 9)),
        ("meals without receipts", ("manual", 10)),
        ("baggage delay waiting period", ("wording", 4)),
        ("lost passport", ("wording", 6)),
    ],
)
def test_search_finds_the_section_a_handler_would(client, query, first):
    assert search(client, query)[0] == first


def test_search_returns_at_most_three(client):
    assert len(search(client, "claim payment documents receipts")) == 3


def test_search_with_nothing_in_common(client):
    assert search(client, "zz") == []


def test_reads_one_section(client):
    section = client.get("/api/documents/manual/sections/10").json()
    assert section["title"] == "Meals without receipts"
    assert section["text"].startswith("Customers stuck at an airport")
    assert "$35 per traveler" in section["text"]
    assert "## 11." not in section["text"]


def test_the_last_section_runs_to_the_end(client):
    section = client.get("/api/documents/wording/sections/12").json()
    assert section["title"] == "Definitions"
    assert len(section["text"]) > 100


def test_the_opening_holds_the_version(client):
    section = client.get("/api/documents/wording/sections/0").json()
    assert section["title"] == "Version and scope"
    assert "Version 2026.1" in section["text"]


def test_a_section_that_isnt_there(client):
    assert client.get("/api/documents/manual/sections/99").status_code == 404


def test_a_document_that_isnt_there(client):
    assert client.get("/api/documents/guide/sections/1").status_code == 422


def test_a_section_step_must_name_a_section(client):
    start(client, "CLM-1001")
    step = {"thread_id": "t", "kind": "section", "text": "manual 9"}
    assert client.post("/api/claims/CLM-1001/steps", json=step).status_code == 422
