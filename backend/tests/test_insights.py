import pytest

from backend import db

SECTION_READ = (
    '{"document": "manual", "document_title": "Claims manual", "number": 9,'
    ' "title": "Repeat claims"}'
)
REFUSAL = "Refused (409): A payout over $1,000.00 waits for a handler's sign-off"


def insights(client):
    response = client.get("/api/insights")
    assert response.status_code == 200
    return response.json()


def add_steps(claim_id, thread_id, steps):
    """Record steps at set times, given as (second, kind, text)."""
    with db.connect() as conn:
        conn.executemany(
            "INSERT INTO steps (claim_id, thread_id, kind, text, recorded_at)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (claim_id, thread_id, kind, text, f"2026-10-19T10:00:{s:02d}+00:00")
                for s, kind, text in steps
            ],
        )


def decide(client, claim_id, decision, payout, section="Section 3, Trip Delay"):
    client.post(f"/api/claims/{claim_id}/start")
    response = client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": decision,
            "payout": payout,
            "reasons": "The agent's reasons.",
            "policy_section": section,
        },
    )
    assert response.status_code == 200


@pytest.fixture
def worked(client):
    """CLM-1001 straight through, CLM-1002 held for sign-off after a refused
    payment, CLM-1003 declined and CLM-1010 referred."""
    insights(client)
    add_steps(
        "CLM-1001",
        "CLM-1001-a",
        [
            (0, "tool_call", 'get_claim {"claim_id": "CLM-1001"}'),
            (2, "tool_result", "{}"),
            (4, "tool_call", 'decide_claim {"claim_id": "CLM-1001"}'),
            (6, "tool_result", "{}"),
            (8, "tool_call", 'pay_claim {"claim_id": "CLM-1001"}'),
            (9, "tool_result", "{}"),
            (10, "reply", "Approved and paid $420.00."),
        ],
    )
    add_steps(
        "CLM-1002",
        "CLM-1002-a",
        [
            (0, "tool_call", 'decide_claim {"claim_id": "CLM-1002"}'),
            (1, "tool_result", "{}"),
            (2, "tool_call", 'pay_claim {"claim_id": "CLM-1002"}'),
            (4, "tool_result", REFUSAL),
        ],
    )
    decide(client, "CLM-1001", "approve", 420)
    client.post("/api/claims/CLM-1001/payment", json={"amount": 420})
    decide(client, "CLM-1002", "approve", 1150, "Section 5, Baggage")
    decide(
        client,
        "CLM-1003",
        "decline",
        0,
        "Section 7, Emergency Medical; Section 9, Exclusions",
    )
    decide(client, "CLM-1010", "refer", 0, "Section 7, Emergency Medical")
    return insights(client)


def test_before_any_work(client):
    assert insights(client) == {
        "totals": {
            "claims": 25,
            "decided": 0,
            "straight_through": 0,
            "sign_offs": 0,
            "referred": 0,
            "waiting_for_handler": 0,
            "tool_calls": 0,
            "refused": 0,
            "median_seconds": None,
            "longest_seconds": None,
            "claimed": 0,
            "approved": 0,
            "paid": 0,
            "held": 0,
        },
        "by_type": [],
        "tools": [],
        "sections": [],
        "claims": [],
    }


def test_totals(worked):
    totals = worked["totals"]
    assert totals["decided"] == 4
    assert totals["straight_through"] == 2
    assert totals["sign_offs"] == 1
    assert totals["referred"] == 1
    assert totals["waiting_for_handler"] == 2
    assert totals["claimed"] == 420 + 1150 + 3800 + 1350
    assert totals["approved"] == 1570
    assert totals["paid"] == 420
    assert totals["held"] == 1150


def test_decisions_by_type(worked):
    assert worked["by_type"] == [
        {"claim_type": "baggage", "approve": 1, "decline": 0, "refer": 0},
        {"claim_type": "emergency_medical", "approve": 0, "decline": 1, "refer": 1},
        {"claim_type": "trip_delay", "approve": 1, "decline": 0, "refer": 0},
    ]


def test_tools_and_refusals(worked):
    assert worked["tools"] == [
        {"tool": "decide_claim", "calls": 2, "refused": 0},
        {"tool": "pay_claim", "calls": 2, "refused": 1},
        {"tool": "get_claim", "calls": 1, "refused": 0},
    ]
    assert worked["totals"]["tool_calls"] == 5
    assert worked["totals"]["refused"] == 1
    held = next(c for c in worked["claims"] if c["claim_id"] == "CLM-1002")
    assert held["refused"] == 1
    assert held["status"] == "awaiting_sign_off"


def test_time_per_claim(worked):
    claims = {c["claim_id"]: c for c in worked["claims"]}
    assert list(claims) == ["CLM-1001", "CLM-1002"]
    assert claims["CLM-1001"]["seconds"] == 10
    assert claims["CLM-1001"]["decision"] == "approve"
    assert claims["CLM-1002"]["seconds"] == 4
    assert worked["totals"]["median_seconds"] == 7
    assert worked["totals"]["longest_seconds"] == 10


def test_sections_cited(worked):
    assert worked["sections"][0] == {
        "section": "Section 7, Emergency Medical",
        "claims": 2,
    }
    assert {s["section"] for s in worked["sections"]} == {
        "Section 7, Emergency Medical",
        "Section 3, Trip Delay",
        "Section 5, Baggage",
        "Section 9, Exclusions",
    }


def test_only_the_latest_run_counts(client):
    insights(client)
    add_steps(
        "CLM-1004",
        "CLM-1004-stopped",
        [(0, "tool_call", "get_claim {}"), (30, "tool_result", "{}")],
    )
    add_steps(
        "CLM-1004",
        "CLM-1004-again",
        [(40, "tool_call", "get_claim {}"), (45, "tool_result", "{}")],
    )
    [claim] = insights(client)["claims"]
    assert claim["seconds"] == 5
    assert claim["tool_calls"] == 1
    assert claim["decision"] is None


def test_sections_read_are_not_tool_calls(client):
    insights(client)
    add_steps(
        "CLM-1005",
        "CLM-1005-a",
        [
            (0, "tool_call", 'read_section {"document": "manual", "number": 9}'),
            (1, "tool_result", "{}"),
            (1, "section", SECTION_READ),
            (2, "tool_call", "get_claim {}"),
            (3, "tool_result", "{}"),
        ],
    )
    [claim] = insights(client)["claims"]
    assert claim["tool_calls"] == 2
    assert {t["tool"] for t in insights(client)["tools"]} == {
        "read_section",
        "get_claim",
    }
