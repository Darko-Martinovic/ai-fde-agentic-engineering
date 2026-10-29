"""The backend's API, as the claim agent and the agent's service use it: one
function per operation, named after it, through the connection in
`connection.py`. A refusal raises `connection.Refused`; any other error raises
httpx's. It has no way to the scores, the settings or the handlers' decisions."""

from typing import Any

from agent.connection import send


def list_claims() -> list[dict[str, Any]]:
    return send("GET", "/api/claims").json()


def get_claim(claim_id: str) -> dict[str, Any]:
    return send("GET", f"/api/claims/{claim_id}").json()


def get_policy(policy_id: str) -> dict[str, Any]:
    return send("GET", f"/api/policies/{policy_id}").json()


def get_customer(customer_id: str) -> dict[str, Any]:
    return send("GET", f"/api/customers/{customer_id}").json()


def get_version(number: int) -> dict[str, Any]:
    return send("GET", f"/api/versions/{number}").json()


def get_current_version() -> dict[str, Any]:
    return send("GET", "/api/versions/current").json()


def get_screening_model() -> dict[str, Any]:
    return send("GET", "/api/screening-model").json()


def list_sections() -> list[dict[str, Any]]:
    return send("GET", "/api/documents/sections").json()


def search_documents(query: str) -> list[dict[str, Any]]:
    return send("GET", "/api/documents/search", query={"query": query}).json()


def read_section(document: str, number: int) -> dict[str, Any]:
    return send("GET", f"/api/documents/{document}/sections/{number}").json()


def start_claim(claim_id: str, run_id: int | None, thread_id: str) -> dict[str, Any]:
    body = {"run_id": run_id, "thread_id": thread_id}
    return send("POST", f"/api/claims/{claim_id}/start", body).json()


def fail_claim(claim_id: str, thread_id: str, reason: str) -> dict[str, Any]:
    body = {"thread_id": thread_id, "reason": reason}
    return send("POST", f"/api/claims/{claim_id}/failure", body).json()


def create_dispatch(agents: int) -> dict[str, Any]:
    return send("POST", "/api/runs/dispatches", {"agents": agents}).json()


def create_evaluation(evaluation_set: str, tiny: bool, agents: int) -> dict[str, Any]:
    body = {"evaluation_set": evaluation_set, "tiny": tiny, "agents": agents}
    return send("POST", "/api/runs/evaluations", body).json()


def record_run_claims(run_id: int, claim_ids: list[str]) -> None:
    send("PUT", f"/api/runs/{run_id}/claims", {"claim_ids": claim_ids})


def finish_run(run_id: int, stopped: bool) -> dict[str, Any]:
    return send("POST", f"/api/runs/{run_id}/finish", {"stopped": stopped}).json()


def stop_runs() -> list[int]:
    return send("POST", "/api/runs/stop-all").json()["run_ids"]


def record_model_call(claim_id: str, call: dict[str, Any]) -> None:
    send("POST", f"/api/claims/{claim_id}/model-calls", call)


def record_work_time(claim_id: str, spell: dict[str, Any]) -> None:
    send("POST", f"/api/claims/{claim_id}/work-times", spell)


def record_step(claim_id: str, thread_id: str, kind: str, text: str) -> None:
    send(
        "POST",
        f"/api/claims/{claim_id}/steps",
        {"thread_id": thread_id, "kind": kind, "text": text},
    )


def decide_claim(claim_id: str, decision: dict[str, Any]) -> dict[str, Any]:
    return send("POST", f"/api/claims/{claim_id}/decision", decision).json()


def pay_claim(claim_id: str, amount: float) -> dict[str, Any]:
    return send("POST", f"/api/claims/{claim_id}/payment", {"amount": amount}).json()


def calculate_payout(claim_id: str, claim: dict[str, Any]) -> dict[str, Any]:
    return send("POST", f"/api/claims/{claim_id}/payout", claim).json()
