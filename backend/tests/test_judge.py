import json

import httpx
import pytest
from openrouter import OpenRouter

from backend import judge
from backend.run_models import Grade
from backend.tests.judge_answers import ANSWER, REAL_ASK
from settings import setting

HANDLER = {
    "decision": "approve",
    "reason": "The delay was over six hours and every cost has a receipt.",
    "reference": "Policy wording 3, Trip Delay",
}
AGENT = {
    "decision": "approve",
    "reason": "A 19-hour delay is covered; the receipts total $420.00.",
    "section": "Policy wording 3, Trip Delay",
}


@pytest.fixture
def judge_answers(monkeypatch):
    """The real call to the judge, on a client whose requests are answered
    here, one answer for each request; the requests it sent."""
    sent: list[httpx.Request] = []
    answers: list[httpx.Response | Exception] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        reply = answers.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    client = OpenRouter(
        api_key="test-key", client=httpx.Client(transport=httpx.MockTransport(answer))
    )
    monkeypatch.setattr(judge, "client", lambda: client)
    monkeypatch.setattr(judge, "ask", REAL_ASK)
    return sent, answers


def test_the_judge_is_asked_the_three_questions_about_the_state(judge_answers):
    sent, answers = judge_answers
    answers.append(httpx.Response(200, json=ANSWER))
    grade = judge.grade(HANDLER, AGENT)
    assert grade == Grade(2.2, "B", 0.8, 0.3, 0.00002)
    [request] = sent
    assert str(request.url) == f"{setting('JUDGE_URL')}/api/alpha/decisions"
    body = json.loads(request.content)
    assert body["model"] == setting("JUDGE_MODEL")
    assert body["state"] == {"handler": HANDLER, "agent": AGENT}
    assert set(body["questions"]) == {"grade", "same_grounds", "same_section"}
    assert "`agent.section`" in body["questions"]["same_section"]["instructions"]
    assert request.extensions["timeout"]["read"] == 10


def test_the_letter_is_the_most_likely_level_never_the_score_rounded(judge_answers):
    _, answers = judge_answers
    unsure = json.loads(json.dumps(ANSWER))
    unsure["answers"]["grade"] |= {
        "score": 1.5,
        "probabilities": {"0": 0.4, "1": 0.05, "2": 0.2, "3": 0.35},
    }
    answers.append(httpx.Response(200, json=unsure))
    grade = judge.grade(HANDLER, AGENT)
    assert grade is not None
    assert (grade.grade, grade.letter) == (1.5, "F")


@pytest.mark.parametrize(
    "reply",
    [
        httpx.ReadTimeout("slow"),
        httpx.Response(500, json={"error": {"message": "down"}}),
        httpx.Response(200, json=ANSWER | {"answers": {}}),
    ],
    ids=["a timeout", "an error", "no grade"],
)
def test_a_claim_the_judge_cant_grade_is_left_ungraded_after_one_request(
    judge_answers, reply
):
    sent, answers = judge_answers
    answers.extend([reply, httpx.Response(200, json=ANSWER)])
    assert judge.grade(HANDLER, AGENT) is None
    assert len(sent) == 1


def test_the_judges_address_comes_from_the_settings(judge_answers, monkeypatch):
    sent, answers = judge_answers
    monkeypatch.setenv("JUDGE_URL", "http://judge.test")
    answers.append(httpx.Response(200, json=ANSWER))
    judge.grade(HANDLER, AGENT)
    assert str(sent[0].url) == "http://judge.test/api/alpha/decisions"
