import httpx
import pytest
from fastapi.testclient import TestClient

from agent import api, connection, improver_api, service
from backend.tests.sign_ins import AGENT_KEY


@pytest.fixture
def sent(monkeypatch):
    """The requests the agent's clients send, each answered with an empty
    object, in place of the backend."""
    requests = []

    def answer(request):
        requests.append(request)
        return httpx.Response(200, json={})

    monkeypatch.setattr(
        connection,
        "client",
        lambda: httpx.Client(
            base_url="http://backend", transport=httpx.MockTransport(answer)
        ),
    )
    return requests


def test_every_request_carries_the_agents_key(sent):
    api.list_sections()
    improver_api.get_round(1)
    assert [request.headers[connection.KEY_HEADER] for request in sent] == [
        AGENT_KEY
    ] * 2


def test_the_key_is_read_as_each_request_is_sent(sent, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_API_KEY", "loaded-later")
    api.list_sections()
    assert sent[0].headers[connection.KEY_HEADER] == "loaded-later"


def test_the_service_refuses_to_start_without_the_key(monkeypatch):
    monkeypatch.delenv("UNDERCOVER_API_KEY")
    with (
        pytest.raises(RuntimeError, match=r"UNDERCOVER_API_KEY is missing"),
        TestClient(service.app),
    ):
        pass
