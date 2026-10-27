"""Starting and stopping a run from the dashboard: the backend asks the agent's
service, here a stand-in for its HTTP calls, and writes nothing itself."""

import httpx
import pytest

from backend import agent_service

LUNA = "openrouter:openai/gpt-6-luna"


@pytest.fixture
def service(monkeypatch):
    """The agent's service as the backend reaches it: each call is recorded
    and answered with the response set for its path."""
    asked = []
    answers = {}

    def post(url, json=None, timeout=None):
        asked.append((url.removeprefix(agent_service.url("")), json))
        answer = answers[asked[-1][0]]
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, httpx.Response):
            return answer
        return httpx.Response(answer[0], json=answer[1])

    monkeypatch.setattr(agent_service.httpx, "post", post)
    return asked, answers


def test_a_start_asks_the_service_once_and_writes_nothing(client, service):
    asked, answers = service
    answers["/api/dispatches"] = (202, {"agents": 7, "model": LUNA})
    started = client.post("/api/dispatches", json={"agents": 7, "model": LUNA})
    assert started.status_code == 202
    assert started.json() == {"agents": 7, "model": LUNA}
    assert asked == [("/api/dispatches", {"agents": 7, "model": LUNA})]
    assert client.get("/api/dispatches/latest").json() is None


def test_the_services_refusal_comes_back(client, service):
    _, answers = service
    detail = "A dispatch or an evaluation is already running"
    answers["/api/dispatches"] = (409, {"detail": detail})
    refused = client.post("/api/dispatches", json={"agents": 3, "model": LUNA})
    assert (refused.status_code, refused.json()["detail"]) == (409, detail)


def test_a_service_that_isnt_running_says_so(client, service):
    _, answers = service
    answers["/api/dispatches"] = httpx.ConnectError("refused")
    down = client.post("/api/dispatches", json={"agents": 3, "model": LUNA})
    assert down.status_code == 503
    assert down.json()["detail"] == "The agent's service isn't running"


@pytest.mark.parametrize(
    "body",
    [
        {"agents": 0, "model": LUNA},
        {"agents": 26, "model": LUNA},
        {"agents": 3, "model": "someone/else"},
    ],
)
def test_a_start_needs_one_to_25_agents_and_a_model_allowed(client, service, body):
    asked, _ = service
    assert client.post("/api/dispatches", json=body).status_code == 422
    assert asked == []


def test_a_stop_is_passed_on_with_the_services_answer(client, service):
    asked, answers = service
    answers["/api/runs/stop"] = (202, {"stopping": True})
    stopping = client.post("/api/runs/stop-request")
    assert (stopping.status_code, stopping.json()) == (202, {"stopping": True})
    assert asked == [("/api/runs/stop", {})]
    answers["/api/runs/stop"] = (
        409,
        {"detail": "No dispatch or evaluation is running"},
    )
    nothing = client.post("/api/runs/stop-request")
    assert nothing.status_code == 409
    assert nothing.json()["detail"] == "No dispatch or evaluation is running"


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(500, text="Internal Server Error"),
        httpx.ReadTimeout("slow"),
    ],
)
def test_a_service_that_fails_is_a_502(client, service, answer):
    _, answers = service
    answers["/api/dispatches"] = answer
    failed = client.post("/api/dispatches", json={"agents": 3, "model": LUNA})
    assert failed.status_code == 502
    assert failed.json()["detail"] == "The agent's service failed"
