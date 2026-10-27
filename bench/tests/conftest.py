import pytest
from fastapi.testclient import TestClient

from agent import harness, service
from agent.tests.conftest import backend  # noqa: F401 - the agent's backend
from backend import agent_service
from backend.main import app
from bench import backend as bench_backend


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    """Tests never call a model: a test that needs one gives it a stub."""

    def refuse(model):
        raise AssertionError(f"A test tried to call {model.spec}")

    monkeypatch.setattr(harness, "chat_model", refuse)


@pytest.fixture(autouse=True)
def evaluations(backend, monkeypatch, memory_saver):  # noqa: F811 - the fixture above
    """The comparison reaches the real backend in process, and the backend's
    start of an evaluation reaches the agent's service in process too, which
    works it before the start returns."""
    monkeypatch.setattr(bench_backend, "client", lambda: TestClient(app))

    def start(evaluation_set, tiny, agents, model):
        asked = service.EvaluationIn(
            evaluation_set=evaluation_set, tiny=tiny, agents=agents, model=model
        )
        service.RUNNING.acquire()
        service.work_a_run(asked, lambda: memory_saver)
        return {"agents": agents, "model": model}

    monkeypatch.setattr(agent_service, "start_evaluation", start)
