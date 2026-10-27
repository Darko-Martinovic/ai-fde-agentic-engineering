"""The backend's API, as the agent uses it: one function per operation, named
after it. A refusal raises Refused; any other error raises httpx's."""

import json
from typing import Any

import httpx

from settings import setting


def client() -> httpx.Client:
    """Return a client for the backend at UNDERCOVER_API."""
    return httpx.Client(base_url=setting("UNDERCOVER_API"), timeout=30)


class Refused(Exception):
    """The backend refused a request, with its status and its reason."""

    def __init__(self, status: int, detail: object) -> None:
        # FastAPI's detail is a message, or a list of errors for invalid input
        reason = detail if isinstance(detail, str) else json.dumps(detail)
        super().__init__(f"Refused ({status}): {reason}")
        self.status = status
        self.detail = detail


def send(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    query: dict[str, str] | None = None,
) -> httpx.Response:
    with client() as backend:
        response = backend.request(method, path, json=body, params=query)
    if response.is_client_error:
        raise Refused(response.status_code, response.json()["detail"])
    return response.raise_for_status()


def list_claims() -> list[dict[str, Any]]:
    return send("GET", "/api/claims").json()


def get_claim(claim_id: str) -> dict[str, Any]:
    return send("GET", f"/api/claims/{claim_id}").json()


def get_policy(policy_id: str) -> dict[str, Any]:
    return send("GET", f"/api/policies/{policy_id}").json()


def get_customer(customer_id: str) -> dict[str, Any]:
    return send("GET", f"/api/customers/{customer_id}").json()


def get_instructions(agent: str) -> str:
    return send("GET", f"/api/instructions/{agent}").text


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


def start_run(mode: str, cap: int, model: str) -> dict[str, Any]:
    body = {"mode": mode, "cap": cap, "model": model}
    return send("POST", "/api/runs", body).json()


def get_latest_run() -> dict[str, Any] | None:
    return send("GET", "/api/runs/latest").json()


def write_todos(run_id: int, todos: list[dict[str, str]]) -> None:
    send("PUT", f"/api/runs/{run_id}/todos", {"todos": todos})


def finish_run(run_id: int, summary: str) -> dict[str, Any]:
    return send("POST", f"/api/runs/{run_id}/finish", {"summary": summary}).json()


def record_usage(run_id: int, usage: dict[str, Any]) -> None:
    send("POST", f"/api/runs/{run_id}/usage", usage)


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
