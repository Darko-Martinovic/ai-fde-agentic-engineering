import pytest
from fastapi.testclient import TestClient
from langfuse import Langfuse
from langfuse._client.resource_manager import LangfuseResourceManager
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agent import api, connection, dispatcher, graph
from backend import agent_service
from backend.main import app


@pytest.fixture(autouse=True)
def backend(tmp_path, monkeypatch):
    """Point the agent at the real backend, in process, on a fresh database. The
    backend's call to the agent's service after a review goes nowhere; the tests
    call the service themselves."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "undercover.db"))
    monkeypatch.setattr(connection, "client", lambda: TestClient(app))
    monkeypatch.setattr(graph, "RETRY_DELAY", 0)
    monkeypatch.setattr(agent_service, "resume_claim", lambda claim_id: None)
    return TestClient(app)


@pytest.fixture(autouse=True)
def no_waits(monkeypatch):
    """The dispatcher's RetryPolicy, with its three tries, but no waits between
    them, so no test sleeps through the backoff."""
    monkeypatch.setattr(
        dispatcher, "RETRY", dispatcher.RETRY._replace(initial_interval=0, jitter=False)
    )


@pytest.fixture
def run(backend):
    """A dispatch to work claims in, on a free model."""
    return api.create_dispatch(3)["run_id"]


@pytest.fixture
def traces(monkeypatch):
    """Trace to memory in place of Langfuse, and read back the spans finished."""
    monkeypatch.delenv("LANGFUSE_TRACING_ENABLED")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    exporter = InMemorySpanExporter()
    langfuse = Langfuse(tracer_provider=TracerProvider(), span_exporter=exporter)

    def finished():
        langfuse.flush()
        return exporter.get_finished_spans()

    yield finished
    # Langfuse keeps one client per key for the process. It has no public way to
    # forget one, so this uses its private resource manager.
    LangfuseResourceManager.reset()
