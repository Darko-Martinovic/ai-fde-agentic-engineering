"""Who signed in: a Supabase access token, checked against the public keys the
project publishes under VITE_SUPABASE_URL. The project signs with asymmetric
keys, so the backend needs no secret. The only module that reaches Supabase
Auth."""

from functools import cache

import jwt
from fastapi import HTTPException

from settings import setting

AUDIENCE = "authenticated"
KEYS_PATH = "/auth/v1/.well-known/jwks.json"
ALGORITHMS = ["ES256", "RS256"]
# What a token must carry for its handler to be found
REQUIRED_CLAIMS = ["exp", "aud", "email"]
# Seconds a fetch of the public keys may take, while a request waits
KEYS_TIMEOUT_SECONDS = 5
# Supabase's clock and ours differ a little, so a token issued a moment ago by
# Supabase's clock can read as issued in the future by ours
CLOCK_SKEW_SECONDS = 30


@cache
def keys() -> jwt.PyJWKClient:
    """The project's public keys, fetched once and cached by the client."""
    return jwt.PyJWKClient(
        f"{setting('VITE_SUPABASE_URL')}{KEYS_PATH}", timeout=KEYS_TIMEOUT_SECONDS
    )


def signed_in_email(token: str) -> str | None:
    """The email of the user a valid access token was issued to, or None when
    it isn't signed by one of the project's keys, is for another audience, has
    expired or names no email."""
    try:
        key = keys().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key,
            algorithms=ALGORITHMS,
            audience=AUDIENCE,
            leeway=CLOCK_SKEW_SECONDS,
            options={"require": REQUIRED_CLAIMS},
        )
    except jwt.PyJWKClientConnectionError as error:
        raise HTTPException(503, "Sign-ins can't be checked right now") from error
    except jwt.PyJWTError:
        return None
    return claims["email"]
