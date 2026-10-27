"""Checks that hold the Python code to docs/CODE_STANDARDS.md, so a review is not
the only thing that does. The dashboard has the same checks in
dashboard/src/standards.test.ts."""

import ast
import inspect
import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from agent import api
from backend.main import app

ROOT = Path(__file__).resolve().parents[1]
PARTS = ("backend", "agent", "bench")
MAX_LINES = 300
MAX_FUNCTION_LINES = 40

ADDRESS = re.compile(r"https?://|localhost|127\.0\.0\.1")
MODEL_ID = re.compile(r"deepseek|claude-|qwen|gemma|gpt-\d")
ANSWER_KEY = re.compile(r"[\"'][^\"']*evals")
API_PATH = re.compile(r"[\"']/api/")
RUNS_SQL = re.compile(r"\.execute(many|script)?\(")
SQL = re.compile(r"\b(SELECT|INSERT INTO|DELETE FROM)\b|\bUPDATE \w+ SET\b")
# What may write SQL: the store, the schema, and the agent's own tables, those of
# LangGraph's checkpointer, which it makes in the same schema
SQL_OWNERS = ("backend/db.py", "agent/checkpoints.py")
HTTP_CLIENT = re.compile(r"^\s*(import|from) httpx")


def sources(parts: tuple[str, ...] = PARTS) -> Iterator[Path]:
    """Every Python module of the product's parts, leaving out tests, and the
    shared settings."""
    if parts == PARTS:
        yield ROOT / "settings" / "__init__.py"
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


SVG_NAMESPACE = 'xmlns="http://www.w3.org/2000/svg"'


def test_no_address_in_code():
    """Hosts, ports and URLs live in .env.defaults (standard 22). The SVG
    namespace in the comparison's chart is a name, not an address."""
    found = offending(ADDRESS, PARTS)
    assert [line for line in found if SVG_NAMESPACE not in line] == []


def test_no_model_in_code():
    """Models live in models.toml and MODEL_NAME (standard 22)."""
    assert offending(MODEL_ID) == []


def test_nothing_reaches_the_answer_key():
    """Only seeding reads data/evals/, into tables no claim operation reads; the
    agent never sees it, and the comparison reads the backend's scores."""
    assert offending(ANSWER_KEY, PARTS, ("backend/seed.py",)) == []


def test_only_the_api_module_calls_the_backend():
    """The agent reaches the backend only through agent/api.py (standards 7, 15)."""
    allowed = ("agent/api.py",)
    assert offending(API_PATH, ("agent",), allowed) == []
    assert offending(HTTP_CLIENT, ("agent",), allowed) == []


def test_only_one_module_calls_the_backend_from_the_comparison():
    """The model comparison reaches the backend only through bench/backend.py."""
    assert offending(HTTP_CLIENT, ("bench",), ("bench/backend.py",)) == []
    assert offending(API_PATH, ("bench",), ("bench/backend.py",)) == []


def test_only_one_module_calls_the_agents_service():
    """The backend reaches the agent's service only through
    backend/agent_service.py, which names its address once (standards 7, 15)."""
    allowed = ("backend/agent_service.py",)
    assert offending(HTTP_CLIENT, ("backend",), allowed) == []
    assert offending(re.compile(r"UNDERCOVER_AGENT"), ("backend",), allowed) == []


def test_agent_api_is_named_after_the_operations():
    """Each function in agent/api.py is a backend operation, by name (standard 16)."""
    functions = {
        name
        for name, member in inspect.getmembers(api, inspect.isfunction)
        if member.__module__ == api.__name__ and name not in {"client", "send"}
    }
    assert functions <= operation_ids()


def operation_ids() -> set[str]:
    return {
        operation["operationId"]
        for methods in app.openapi()["paths"].values()
        for operation in methods.values()
    }


def camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(word.title() for word in rest)


def test_the_dashboards_api_is_named_after_the_operations():
    """Each key of the dashboard's `api` is a backend operation, in camelCase."""
    source = (ROOT / "dashboard/src/api.ts").read_text(encoding="utf-8")
    block = source[source.index("export const api = {") :]
    keys = set(re.findall(r"^  (\w+):", block, flags=re.MULTILINE))
    assert keys <= {camel(operation) for operation in operation_ids()}


def postman_requests() -> Iterator[dict[str, object]]:
    def walk(items: list[dict[str, object]]) -> Iterator[dict[str, object]]:
        for item in items:
            if "item" in item:
                yield from walk(item["item"])  # type: ignore[arg-type]
            else:
                yield item

    collection = json.loads(
        (ROOT / "backend/postman/undercover.postman_collection.json").read_text(
            encoding="utf-8"
        )
    )
    yield from walk(collection["item"])


def test_postman_names_and_covers_every_operation():
    """Each request names its operation first; every operation has a request."""
    named = [
        re.match(r"`(\w+)`", str(request["request"]["description"]))  # type: ignore[index]
        for request in postman_requests()
    ]
    assert all(named)
    assert {match[1] for match in named if match} == operation_ids()


def test_sql_only_in_the_store():
    """SQL lives in backend/store/, one module per group of tables (standard 17)."""
    in_store = tuple(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "backend/store").glob("*.py")
    )
    assert offending(SQL, ("backend",), SQL_OWNERS + in_store) == []
    assert offending(RUNS_SQL, ("backend", "agent"), SQL_OWNERS + in_store) == []


def long_functions(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        f"{path.name}: {node.name} ({node.end_lineno - node.lineno + 1} lines)"
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and (node.end_lineno or 0) - node.lineno + 1 > MAX_FUNCTION_LINES
    ]


def test_functions_stay_short():
    """A function over 40 lines does more than one job (standards 11, 18)."""
    assert [found for path in sources() for found in long_functions(path)] == []


@pytest.mark.parametrize("path", list(sources()), ids=lambda p: p.name)
def test_modules_stay_short(path):
    """A module over 300 lines does more than one job (standard 18)."""
    assert len(path.read_text(encoding="utf-8").splitlines()) <= MAX_LINES


def test_the_agent_cannot_read_the_scoreboard_or_start_runs():
    """The handlers' decisions reach the scoreboard only, and runs are started
    from the dashboard, never by the agent."""
    kept_out = {
        "list_evaluations",
        "get_evaluation",
        "start_dispatch",
        "start_evaluation",
    }
    assert kept_out <= operation_ids()
    assert not kept_out & set(dir(api))
    reads = re.compile(r"[\"']/api/(evaluations|dispatches)")
    assert offending(reads, ("agent",), ("agent/service.py",)) == []
