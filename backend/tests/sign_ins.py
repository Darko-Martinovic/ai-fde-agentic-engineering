"""Sign-ins for the tests: a key pair made for the test run stands in for the
Supabase project's, so a token signed with it passes backend/auth.py, and each
handler's headers carry one."""

import time

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from backend.agent_key import KEY_HEADER

KEY = ec.generate_private_key(ec.SECP256R1())
KEY_ID = "test-key"
DANA = "dana.whitfield@undercover.example"
MARCUS = "marcus.oyelaran@undercover.example"
PRIYA = "priya.raman@undercover.example"


def claims_for(
    email: str,
    audience: str = "authenticated",
    expires_in: int = 3600,
    clock_ahead: int = 0,
) -> dict[str, object]:
    """What Supabase Auth puts in an access token, on a clock that may be ahead
    of ours."""
    issued = int(time.time()) + clock_ahead
    return {
        "sub": email,
        "email": email,
        "aud": audience,
        "iat": issued,
        "exp": issued + expires_in,
    }


def token(
    email: str,
    key: ec.EllipticCurvePrivateKey = KEY,
    audience: str = "authenticated",
    expires_in: int = 3600,
    clock_ahead: int = 0,
) -> str:
    """An access token for the email, as Supabase Auth would sign it."""
    return signed(claims_for(email, audience, expires_in, clock_ahead), key)


def signed(claims: dict[str, object], key: ec.EllipticCurvePrivateKey = KEY) -> str:
    """Claims signed as Supabase Auth signs them, with the test key's id."""
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": KEY_ID})


def bearer(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def headers(email: str) -> dict[str, str]:
    """The headers a signed-in handler's requests carry."""
    return bearer(token(email))


# The agent's key for the test run, which the root conftest.py sets
AGENT_KEY = "test-agent-key"


def agent_headers() -> dict[str, str]:
    """The headers the agent's side sends: its key."""
    return {KEY_HEADER: AGENT_KEY}


def both_sides(email: str = DANA) -> dict[str, str]:
    """The agent's key and a handler's sign-in at once, for a test client that
    plays the agent's moves and reads the dashboard's pages."""
    return agent_headers() | headers(email)


class Keys(jwt.PyJWKClient):
    """The project's public keys, as Supabase publishes them: the test key's."""

    def __init__(self) -> None:
        super().__init__("https://auth.test/keys")

    def fetch_data(self) -> dict[str, object]:
        public = ECAlgorithm.to_jwk(KEY.public_key(), as_dict=True)
        return {"keys": [public | {"kid": KEY_ID, "alg": "ES256", "use": "sig"}]}
