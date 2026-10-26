"""UnderCover's settings, for every Python part: the environment, filled in from
.env and then .env.defaults at the repo's root. The environment wins over .env,
which wins over .env.defaults, and a value can name another, as ${NAME}. Tests
name .env.defaults alone in UNDERCOVER_ENV_FILES, so they never read .env."""

import os
import re
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
REFERENCE = re.compile(r"\$\{(\w+)\}")

for env_file in os.environ.get("UNDERCOVER_ENV_FILES", ".env,.env.defaults").split(","):
    load_dotenv(ROOT / env_file, interpolate=False)


def setting(name: str) -> str:
    """Return one setting, which must be in the environment or an env file, with
    any ${NAME} in it filled in when it's read, as settings.config.ts does."""
    return REFERENCE.sub(lambda found: setting(found[1]), os.environ[name])


def optional_setting(name: str) -> str | None:
    """Return a setting that may be left out, such as DATABASE_URL, or None when
    it's missing or empty."""
    return setting(name) if os.environ.get(name) else None
