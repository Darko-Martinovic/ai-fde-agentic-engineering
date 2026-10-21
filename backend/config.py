"""The backend's settings: the environment, filled in from .env and then
.env.defaults."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

# The environment wins over .env, which wins over .env.defaults. Tests name
# .env.defaults alone in UNDERCOVER_ENV_FILES, so they never read .env.
for env_file in os.environ.get("UNDERCOVER_ENV_FILES", ".env,.env.defaults").split(","):
    load_dotenv(ROOT / env_file)


def setting(name: str) -> str:
    """Return one setting, which must be in the environment or an env file."""
    return os.environ[name]


def database_path() -> Path:
    """Return the database file in UNDERCOVER_DB, relative to the repo's root."""
    return ROOT / setting("UNDERCOVER_DB")
