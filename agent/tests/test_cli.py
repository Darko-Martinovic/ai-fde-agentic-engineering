from langchain_core.messages import AIMessage

import agent.__main__ as cli
from agent import harness
from agent.tests.stub import StubModel
from backend import db


def reply_only(monkeypatch):
    """Give every run a stub model that reads the claim and replies."""

    def stub(model):
        return StubModel(
            messages=iter(
                [
                    AIMessage(
                        content="",
                        tool_calls=[{"name": "get_claim", "args": {}, "id": "1"}],
                    ),
                    AIMessage(content="Looked at it."),
                ]
            )
        )

    monkeypatch.setattr(harness, "chat_model", stub)


def test_one_claim(backend, monkeypatch, capsys):
    reply_only(monkeypatch)
    cli.main(["CLM-1001"])
    assert capsys.readouterr().out == "CLM-1001: Looked at it.\n"
    assert backend.get("/api/claims/CLM-1001").json()["status"] == "in_progress"


def test_the_queue(backend, monkeypatch, capsys):
    reply_only(monkeypatch)
    backend.get("/api/claims")
    conn = db.connect()
    with conn:
        conn.execute(
            "UPDATE claims SET status = 'decided'"
            " WHERE claim_id NOT IN ('CLM-1003', 'CLM-1004')"
        )
    conn.close()
    cli.main([])
    assert capsys.readouterr().out.splitlines() == [
        "CLM-1003: Looked at it.",
        "CLM-1004: Looked at it.",
    ]
    statuses = {c["claim_id"]: c["status"] for c in backend.get("/api/claims").json()}
    assert statuses["CLM-1003"] == statuses["CLM-1004"] == "in_progress"
