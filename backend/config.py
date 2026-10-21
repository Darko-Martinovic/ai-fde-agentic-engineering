"""The backend's settings, beyond the shared ones in settings.py."""

from pathlib import Path

from settings import ROOT, setting


def database_path() -> Path:
    """Return the database file in UNDERCOVER_DB, relative to the repo's root."""
    return ROOT / setting("UNDERCOVER_DB")
