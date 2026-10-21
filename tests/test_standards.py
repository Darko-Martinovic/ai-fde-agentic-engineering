"""Checks that hold the Python code to docs/CODE_STANDARDS.md, so a review is not
the only thing that does. The dashboard has the same checks in
dashboard/src/standards.test.ts."""

import inspect
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from agent import api
from backend.main import app

ROOT = Path(__file__).resolve().parents[1]
PARTS = ("backend", "agent")
MAX_LINES = 300

ADDRESS = re.compile(r"https?://|localhost|127\.0\.0\.1")
MODEL_ID = re.compile(r"deepseek|claude-|qwen|gemma|gpt-\d")
ANSWER_KEY = re.compile(r"[\"'][^\"']*evals")
API_PATH = re.compile(r"[\"']/api/")
HTTP_CLIENT = re.compile(r"^\s*(import|from) httpx")


def sources(parts: tuple[str, ...] = PARTS) -> Iterator[Path]:
    """Every Python module of the product's parts, leaving out tests."""
    for part in parts:
        for path in sorted((ROOT / part).rglob("*.py")):
            if "tests" not in path.parts:
                yield path


def code_lines(path: Path) -> list[str]:
    """The module's lines, leaving out comments."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line for line in lines if not line.lstrip().startswith("#")]


def offending(
    pattern: re.Pattern[str],
    parts: tuple[str, ...] = PARTS,
    allowed: tuple[str, ...] = (),
) -> list[str]:
    """The lines, outside the modules allowed, that match the pattern."""
    return [
        f"{path.relative_to(ROOT)}: {line.strip()}"
        for path in sources(parts)
        if path.relative_to(ROOT).as_posix() not in allowed
        for line in code_lines(path)
        if pattern.search(line)
    ]


def test_no_address_in_code():
    """Hosts, ports and URLs live in .env.defaults (standard 22)."""
    assert offending(ADDRESS) == []


def test_no_model_in_code():
    """Models live in models.toml and MODEL_NAME (standard 22)."""
    assert offending(MODEL_ID) == []


def test_nothing_reaches_the_answer_key():
    """The agent and the backend never see data/evals/."""
    assert offending(ANSWER_KEY) == []


def test_only_the_api_module_calls_the_backend():
    """The agent reaches the backend only through agent/api.py (standards 7, 15)."""
    allowed = ("agent/api.py",)
    assert offending(API_PATH, ("agent",), allowed) == []
    assert offending(HTTP_CLIENT, ("agent",), allowed) == []


def test_agent_api_is_named_after_the_operations():
    """Each function in agent/api.py is a backend operation, by name (standard 16)."""
    operations = {
        operation["operationId"]
        for methods in app.openapi()["paths"].values()
        for operation in methods.values()
    }
    functions = {
        name
        for name, member in inspect.getmembers(api, inspect.isfunction)
        if member.__module__ == api.__name__ and name not in {"client", "send"}
    }
    assert functions <= operations


@pytest.mark.parametrize("path", list(sources()), ids=lambda p: p.name)
def test_modules_stay_short(path):
    """A module over 300 lines does more than one job (standard 18)."""
    assert len(path.read_text(encoding="utf-8").splitlines()) <= MAX_LINES
