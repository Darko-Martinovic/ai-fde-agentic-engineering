import base64
import hashlib
import hmac
import json

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from backend import agent_service, auth
from backend.tests.sign_ins import (
    DANA,
    KEY,
    KEY_ID,
    MARCUS,
    PRIYA,
    bearer,
    claims_for,
    headers,
    signed,
    token,
)
from backend.tests.workflow_steps import approved, referred

# The real key client, before the tests' stand-in takes its place
REAL_KEYS = auth.keys
LUNA = "openrouter:openai/gpt-6-luna"

# Every action a handler takes, each of which needs a signed-in handler
HANDLER_ACTIONS = [
    ("/api/claims/CLM-1003/review", {"approved": True, "note": ""}),
    (
        "/api/claims/CLM-1010/handler-decision",
        {"decision": "decline", "payout": 0, "reasons": "Not covered."},
    ),
    ("/api/dispatches", {"agents": 3, "model": LUNA}),
    ("/api/runs/stop-request", None),
    (
        "/api/evaluations",
        {"evaluation_set": "evaluation", "tiny": True, "agents": 3, "model": LUNA},
    ),
    ("/api/improvement/rounds", None),
    ("/api/improvement/rounds/1/stop", None),
    ("/api/improvement/rounds/1/proposals/1/approval", None),
    ("/api/improvement/rounds/1/proposals/1/rejection", {"note": "No."}),
]


def encoded(part: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(json.dumps(part).encode()).rstrip(b"=").decode()


def hs256_with_the_public_key() -> str:
    """A token signed with HMAC, using the public key as its secret: the old
    trick against a check that trusts the token's own algorithm."""
    public = KEY.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    head = f"{encoded({'alg': 'HS256', 'kid': KEY_ID})}.{encoded(claims_for(DANA))}"
    mac = hmac.new(public, head.encode(), hashlib.sha256).digest()
    return f"{head}.{base64.urlsafe_b64encode(mac).rstrip(b'=').decode()}"


def unsigned() -> str:
    return f"{encoded({'alg': 'none', 'kid': KEY_ID})}.{encoded(claims_for(DANA))}."


def test_a_signed_in_handler_is_found_by_their_email(client):
    me = client.get("/api/me", headers=headers(DANA))
    assert me.status_code == 200
    assert me.json() == {
        "handler_id": "HND-01",
        "name": "Dana Whitfield",
        "role": "Senior Claims Handler",
        "email": DANA,
        "can_approve_over_limit": True,
    }


@pytest.mark.parametrize(
    "sent",
    [
        {},
        bearer("not-a-token"),
        bearer(token(DANA, key=ec.generate_private_key(ec.SECP256R1()))),
        bearer(token(DANA, expires_in=-120)),
        bearer(token(DANA, audience="anon")),
        bearer(signed({k: v for k, v in claims_for(DANA).items() if k != "email"})),
        bearer(signed({k: v for k, v in claims_for(DANA).items() if k != "exp"})),
        bearer(hs256_with_the_public_key()),
        bearer(unsigned()),
    ],
    ids=[
        "no token",
        "not a token",
        "another key",
        "expired",
        "another audience",
        "no email",
        "no expiry",
        "HS256 with the public key",
        "unsigned",
    ],
)
def test_without_a_valid_token_nobody_is_signed_in(agent_client, sent):
    refused = agent_client.get("/api/me", headers=sent)
    assert (refused.status_code, refused.json()["detail"]) == (
        401,
        "Sign in as a handler first",
    )


def test_a_token_from_a_clock_a_little_ahead_is_accepted(client):
    """Supabase's clock may be a second or two ahead of ours."""
    ahead = bearer(token(DANA, clock_ahead=5))
    assert client.get("/api/me", headers=ahead).status_code == 200


def test_a_token_for_someone_who_isnt_a_handler_is_refused(client):
    refused = client.get("/api/me", headers=headers("someone@example.com"))
    assert (refused.status_code, refused.json()["detail"]) == (
        403,
        "someone@example.com isn't one of UnderCover's handlers",
    )


def test_sign_ins_that_cant_be_checked_say_so(client, monkeypatch):
    class Unreachable:
        def get_signing_key_from_jwt(self, token):
            raise jwt.PyJWKClientConnectionError("refused")

    monkeypatch.setattr(auth, "keys", Unreachable)
    refused = client.get("/api/me", headers=headers(DANA))
    assert refused.status_code == 503


def test_the_keys_are_fetched_from_the_supabase_project(monkeypatch):
    monkeypatch.setenv("VITE_SUPABASE_URL", "https://project.supabase.co")
    REAL_KEYS.cache_clear()
    try:
        assert REAL_KEYS().uri == (
            "https://project.supabase.co/auth/v1/.well-known/jwks.json"
        )
        assert REAL_KEYS() is REAL_KEYS()
    finally:
        REAL_KEYS.cache_clear()


def test_every_handler_action_needs_a_sign_in_and_does_nothing_without(
    client, agent_client, resumed, monkeypatch
):
    asked = []

    def service(url, json=None, timeout=None):
        asked.append(url)
        return httpx.Response(202, json=json or {})

    monkeypatch.setattr(agent_service.httpx, "post", service)
    approved(client, "CLM-1003", 3750)
    referred(client, "CLM-1010")
    before = client.get("/api/claims").json()
    for path, body in HANDLER_ACTIONS:
        assert agent_client.post(path, json=body).status_code == 401, path
    assert client.get("/api/claims").json() == before
    assert (asked, resumed) == ([], [])


def test_seeding_stores_each_handlers_email_and_whether_they_are_senior(client):
    seniors = {
        email: client.get("/api/me", headers=headers(email)).json()
        for email in (DANA, MARCUS, PRIYA)
    }
    assert {
        email: (handler["name"], handler["can_approve_over_limit"])
        for email, handler in seniors.items()
    } == {
        DANA: ("Dana Whitfield", True),
        MARCUS: ("Marcus Oyelaran", False),
        PRIYA: ("Priya Raman", False),
    }


def test_the_handlers_list_names_them_without_their_emails(client):
    listed = client.get("/api/handlers").json()
    assert listed[0] == {
        "handler_id": "HND-01",
        "name": "Dana Whitfield",
        "role": "Senior Claims Handler",
    }
