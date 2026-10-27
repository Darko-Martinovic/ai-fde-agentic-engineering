"""The UnderCover backend: the app, put together from its routers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from anyio import to_thread
from fastapi import FastAPI

from backend import (
    agent_models,
    claims,
    documents,
    evaluations,
    insights,
    records,
    reviews,
    runs,
    usage,
    workflow,
)
from settings import setting


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Give the routes enough threads for every request at once. A request
    waits on a thread for one of the database's few connections, and its route
    needs another thread to run: with too few, the requests waiting take every
    thread, and those holding a connection can't finish, so the backend stalls
    while many claim agents work at once."""
    to_thread.current_default_thread_limiter().total_tokens = int(
        setting("BACKEND_THREADS")
    )
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)
for module in (
    claims,
    records,
    documents,
    workflow,
    usage,
    reviews,
    runs,
    evaluations,
    agent_models,
    insights,
):
    app.include_router(module.router)


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}
