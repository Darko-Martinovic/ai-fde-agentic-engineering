"""The UnderCover backend: the app, put together from its routers."""

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

app = FastAPI(title="UnderCover")
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
