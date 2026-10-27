from anyio import to_thread
from fastapi.testclient import TestClient

from backend.main import app
from settings import setting

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_the_backend_has_a_thread_for_every_request_at_once():
    """Requests wait on a thread for one of the database's few connections, so
    the backend keeps far more threads than claim agents at once."""
    with TestClient(app) as started:
        portal = started.portal
        assert portal is not None
        threads = portal.call(
            lambda: to_thread.current_default_thread_limiter().total_tokens
        )
    assert threads == int(setting("BACKEND_THREADS"))
