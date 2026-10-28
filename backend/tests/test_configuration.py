import pytest

from backend import db
from backend.seed import INSTRUCTIONS
from backend.tests.new_versions import GEMINI, add_version
from backend.tests.round_steps import a_round, evaluate
from backend.version_models import Verdict
from backend.version_scores import version_scores

CLAIM_INSTRUCTIONS = (INSTRUCTIONS / "claim.md").read_text(encoding="utf-8")
LUNA = "openai/gpt-6-luna"


def test_the_claim_agent_runs_as_the_current_version(client):
    current = client.get("/api/versions/current").json()
    assert current == {
        "number": 1,
        "instructions": CLAIM_INSTRUCTIONS,
        "model": LUNA,
        "reasoning_effort": "low",
        "provider": "openrouter",
        "options": {"max_tokens": 16000, "reasoning_effort": "low"},
    }
    assert client.get("/api/versions/1").json() == current


def test_a_version_as_it_runs_holds_no_scores_or_history(client):
    assert set(client.get("/api/versions/1").json()) == {
        "number",
        "instructions",
        "model",
        "reasoning_effort",
        "provider",
        "options",
    }


def test_an_unknown_version_is_not_found(client):
    for path in ("/api/versions/9", "/api/configuration/versions/9"):
        missing = client.get(path)
        assert (missing.status_code, missing.json()["detail"]) == (
            404,
            "Version 9 not found",
        )


def test_the_newest_kept_version_is_current_and_one_under_test_waits(client):
    client.get("/api/claims")
    add_version(CLAIM_INSTRUCTIONS.replace("plain business English", "plain English"))
    add_version(CLAIM_INSTRUCTIONS + "Refer a claim the manual flags.\n", verdict=None)
    assert client.get("/api/versions/current").json()["number"] == 2
    configuration = client.get("/api/configuration").json()
    assert configuration["current"] == 2
    listed = [
        (v["number"], v["status"], v["lines_added"], v["lines_removed"])
        for v in configuration["versions"]
    ]
    assert listed == [
        (3, "under_test", 1, 0),
        (2, "current", 1, 1),
        (1, "kept", 0, 0),
    ]
    assert [m["model"] for m in configuration["models_allowed"]] == [
        LUNA,
        GEMINI,
        "deepseek/deepseek-v4.1-flash",
    ]


def test_a_rolled_back_version_isnt_current(client):
    client.get("/api/claims")
    add_version("# Worse", verdict=Verdict.ROLLED_BACK)
    configuration = client.get("/api/configuration").json()
    assert configuration["current"] == 1
    assert configuration["versions"][0]["status"] == "rolled_back"


def test_a_versions_details_show_what_it_changed_from_its_base(client):
    client.get("/api/claims")
    add_version(CLAIM_INSTRUCTIONS.replace("plain business English", "plain English"))
    details = client.get("/api/configuration/versions/2").json()
    assert (details["based_on"], details["proposed_by"], details["approved_by"]) == (
        1,
        "Round 1",
        "HND-01",
    )
    assert (details["based_on_model"], details["based_on_reasoning_effort"]) == (
        LUNA,
        "low",
    )
    assert (details["model"], details["reasoning_effort"]) == (GEMINI, "minimal")
    [hunk] = details["changes"]
    kinds = [line["kind"] for line in hunk["lines"]]
    assert kinds.count("removed") == kinds.count("added") == 1
    [removed] = [line for line in hunk["lines"] if line["kind"] == "removed"]
    assert "plain business English" in removed["text"]


def test_version_one_was_proposed_by_the_claims_team(client):
    details = client.get("/api/configuration/versions/1").json()
    assert (details["proposed_by"], details["approved_by"], details["changes"]) == (
        "The claims team",
        None,
        [],
    )
    assert details["status"] == "current"


def test_a_version_runs_with_its_reasoning_effort_among_its_options(client):
    client.get("/api/claims")
    add_version("# Version two")
    assert client.get("/api/versions/2").json()["options"] == {
        "reasoning_effort": "minimal"
    }


def test_a_version_on_a_model_no_longer_allowed_says_so(client):
    client.get("/api/claims")
    add_version("# Version two", model="openai/gpt-7")
    refused = client.get("/api/versions/current")
    assert (refused.status_code, refused.json()["detail"]) == (
        409,
        "Version 2's model, openai/gpt-7, isn't one allowed",
    )


def test_a_version_shows_its_held_out_scores_once_a_round_has_evaluated_it(
    client,
):
    first = client.get("/api/configuration").json()["versions"][0]
    assert (first["held_out_accuracy"], first["held_out_grade"]) == (None, None)
    round_id = a_round(client)
    evaluate(client, round_id, "evaluation", right=0.8)
    evaluate(client, round_id, "held_out", right=0.2)
    evaluate(client, round_id, "held_out", right=0.4)
    scored = client.get("/api/configuration").json()["versions"][0]
    with db.engine().connect() as conn:
        held_out = version_scores(conn, 1)["held_out"]
        evaluation = version_scores(conn, 1)["evaluation"]
    assert held_out is not None
    assert evaluation is not None
    assert scored["held_out_accuracy"] == pytest.approx(held_out.accuracy)
    assert scored["held_out_grade"] == pytest.approx(held_out.grade)
    assert held_out.accuracy != evaluation.accuracy
