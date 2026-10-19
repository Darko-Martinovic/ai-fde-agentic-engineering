"""The UnderCover Agent."""

import json
import os
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def call(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Call the backend and return its reply, or its refusal, as text for the model."""
    with backend() as client:
        response = client.request(method, path, json=body)
    if response.is_error:
        return f"Refused ({response.status_code}): {response.json()['detail']}"
    return response.text


@tool
def get_claim(claim_id: str) -> str:
    """Get a claim in full: the story, the items claimed and the documents."""
    return call("GET", f"/api/claims/{claim_id}")


@tool
def get_policy(policy_id: str) -> str:
    """Get a policy, by the claim's policy_id, with its plan's limits and add-ons."""
    return call("GET", f"/api/policies/{policy_id}")


@tool
def get_customer(customer_id: str) -> str:
    """Get a customer, by the claim's customer_id, with their earlier claims."""
    return call("GET", f"/api/customers/{customer_id}")


@tool
def decide_claim(
    claim_id: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    reasons: str,
    policy_section: str,
) -> str:
    """Record the decision on a claim: the payout, two or three sentences of reasons
    and the section of the policy wording it rests on."""
    return call(
        "POST",
        f"/api/claims/{claim_id}/decision",
        {
            "decision": decision,
            "payout": payout,
            "reasons": reasons,
            "policy_section": policy_section,
        },
    )


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay an approved claim its payout. Payouts over $1,000 wait for sign-off."""
    return call("POST", f"/api/claims/{claim_id}/payment", {"amount": amount})


TOOLS = [get_claim, get_policy, get_customer, decide_claim, pay_claim]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def system_prompt(client: httpx.Client) -> str:
    """Join the agent's instructions and the policy wording, both from the API."""
    instructions = client.get("/api/instructions").raise_for_status().text
    wording = client.get("/api/policy-wording").raise_for_status().text
    return f"{instructions}\n\n{wording}"


def steps(message: BaseMessage) -> list[tuple[str, str]]:
    """Turn one message from the agent into the steps the dashboard shows."""
    if isinstance(message, ToolMessage):
        return [("tool_result", str(message.text))]
    if not isinstance(message, AIMessage):
        return []
    found = [("reply", str(message.text))] if message.text else []
    return found + [
        (
            "tool_call",
            f"{tool_call['name']} {json.dumps(tool_call['args'], ensure_ascii=False)}",
        )
        for tool_call in message.tool_calls
    ]


def messages(update: dict[str, Any]) -> list[BaseMessage]:
    """Return the new messages in one update from the agent's stream."""
    return [m for data in update.values() for m in (data or {}).get("messages", [])]


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim, recording each step, and return its final reply."""
    with backend() as client:
        client.post(f"/api/claims/{claim_id}/start").raise_for_status()
        agent = create_agent(
            llm or model(), tools=TOOLS, system_prompt=system_prompt(client)
        )
        reply = ""
        for update in agent.stream(
            {"messages": [{"role": "user", "content": f"Claim {claim_id}"}]},
            config={"configurable": {"thread_id": thread_id}},
            stream_mode="updates",
        ):
            for message in messages(update):
                for kind, text in steps(message):
                    client.post(
                        f"/api/claims/{claim_id}/steps",
                        json={"thread_id": thread_id, "kind": kind, "text": text},
                    ).raise_for_status()
                if isinstance(message, AIMessage) and message.text:
                    reply = str(message.text)
    return reply
