"""The backend's API, as the agent uses it: one function per operation, named
after it. A refusal raises Refused; any other error raises httpx's."""

from typing import Any

import httpx

from agent.config import setting


def client() -> httpx.Client:
    """Return a client for the backend at UNDERCOVER_API."""
    return httpx.Client(base_url=setting("UNDERCOVER_API"), timeout=30)


class Refused(Exception):
    """The backend refused a request, with its status and its reason."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"Refused ({status}): {detail}")
        self.status = status
        self.detail = detail


def send(method: str, path: str, body: dict[str, Any] | None = None) -> httpx.Response:
    with client() as backend:
        response = backend.request(method, path, json=body)
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


def get_instructions() -> str:
    return send("GET", "/api/instructions").text


def get_policy_wording() -> str:
    return send("GET", "/api/policy-wording").text


def start_claim(claim_id: str) -> dict[str, Any]:
    return send("POST", f"/api/claims/{claim_id}/start").json()


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
