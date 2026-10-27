"""Starting a claim in a run, as the agent does, for the backend's tests."""


def a_run(client, cap=25):
    """Return the run that's running, starting one if there's none."""
    latest = client.get("/api/runs/latest").json()
    if latest and latest["status"] == "running":
        return latest["run_id"]
    run = {"mode": "queue", "cap": cap, "model": "test"}
    return client.post("/api/runs", json=run).json()["run_id"]


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
