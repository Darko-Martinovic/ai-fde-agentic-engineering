from langchain_core.messages import AIMessage

import agent.__main__ as cli
from agent import harness
from agent.tests.stub import StubModel
from backend import db


def reply_only(monkeypatch):
    """Give every run a stub model that reads the claim and replies, deciding
    nothing, so each claim fails and goes back in the queue."""

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
    expected = f"CLM-1001: failed, back in the queue ({harness.STOPPED})"
    assert capsys.readouterr().out == expected + "\n"
    run = backend.get("/api/runs/latest").json()
    assert (run["mode"], run["cap"], run["status"]) == ("claim", 1, "finished")
    assert run["summary"] == expected


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
    lines = capsys.readouterr().out.splitlines()
    assert [line.split(":")[0] for line in lines] == ["CLM-1003", "CLM-1004"]
    run = backend.get("/api/runs/latest").json()
    assert (run["mode"], run["cap"], run["claims_started"]) == ("queue", 2, 2)
    assert run["summary"].splitlines() == lines
