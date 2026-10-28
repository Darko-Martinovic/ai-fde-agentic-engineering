"""Starting a claim, in a dispatch as the agent does or on its own, for the
backend's tests."""

DISPATCH = {"agents": 3}


def a_run(client):
    """Return the dispatch that's running, starting one if there's none."""
    latest = client.get("/api/dispatches/latest").json()
    if latest and latest["status"] == "running":
        return latest["run_id"]
    return client.post("/api/runs/dispatches", json=DISPATCH).json()["run_id"]


def start(client, claim_id, run_id=None):
    return client.post(
        f"/api/claims/{claim_id}/start",
        json={"run_id": run_id or a_run(client), "thread_id": f"{claim_id}-test"},
    )


def start_alone(client, claim_id):
    """Start a claim outside any run, as a claim worked on its own is."""
    return client.post(
        f"/api/claims/{claim_id}/start",
        json={"run_id": None, "thread_id": f"{claim_id}-test"},
    )
