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

from agent import api, improver_api
from backend.main import app

ROOT = Path(__file__).resolve().parents[1]
PARTS = ("backend", "agent")
MAX_LINES = 300
MAX_FUNCTION_LINES = 40

ADDRESS = re.compile(r"https?://|localhost|127\.0\.0\.1")
MODEL_ID = re.compile(r"deepseek|claude-|qwen|gemma|gpt-\d|jev-")
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


def test_no_address_in_code():
    """Hosts, ports and URLs live in .env.defaults (standard 22)."""
    assert offending(ADDRESS, PARTS) == []


def test_no_model_in_code():
    """Models live in data/models.json and MODEL_NAME (standard 22)."""
    assert offending(MODEL_ID) == []


def test_only_one_module_reads_the_free_model():
    """MODEL_NAME, a student's free model, is read only by
    backend/free_model.py; the claim agent's model comes from its version."""
    model_name = re.compile(r"MODEL_NAME[\"']")
    assert offending(model_name, PARTS, ("backend/free_model.py",)) == []


def test_the_approval_limit_comes_from_the_settings():
    """The approval limit is a setting: seeding alone reads the company's, and
    no amount of it is written in the backend."""
    company_limit = re.compile(r"payout_approval_limit")
    assert offending(company_limit, ("backend",), ("backend/seed.py",)) == []
    assert offending(re.compile(r"\b1_?000\b"), ("backend",)) == []


def test_only_one_module_calls_the_judge():
    """The judge, its address and the Decisions call are written once, in
    backend/judge.py (standards 7, 15)."""
    judge = re.compile(r"jev-|JUDGE_URL|decisions\.create|from openrouter")
    assert offending(judge, PARTS, ("backend/judge.py",)) == []


def test_nothing_is_left_of_the_model_list_before_versions():
    """The instructions, the model list and the model comparison gave way to
    the versions of the configuration and data/models.json."""
    gone = re.compile(r"get_instructions|list_models|models\.toml|\bbench\b")
    assert offending(gone) == []


def test_nothing_reaches_the_answer_key():
    """Only seeding reads data/evals/, into tables no claim operation reads; the
    agent never sees it."""
    assert offending(ANSWER_KEY, PARTS, ("backend/seed.py",)) == []


def test_only_the_api_modules_call_the_backend():
    """The agent reaches the backend only through its clients, agent/api.py and
    the improver's agent/improver_api.py, on the one connection in
    agent/connection.py, which names its address once (standards 7, 15)."""
    connection = ("agent/connection.py",)
    clients = ("agent/api.py", "agent/improver_api.py")
    assert offending(API_PATH, ("agent",), clients) == []
    assert offending(HTTP_CLIENT, ("agent",), connection) == []
    assert offending(re.compile("UNDERCOVER_API"), ("agent",), connection) == []


def test_only_one_module_checks_sign_ins():
    """The backend reaches Supabase Auth only through backend/auth.py, which
    names its address and the path to its keys once (standards 7, 15)."""
    allowed = ("backend/auth.py",)
    supabase = re.compile(r"VITE_SUPABASE|jwks|PyJWKClient")
    assert offending(supabase, ("backend",), allowed) == []


def test_only_one_module_calls_the_agents_service():
    """The backend reaches the agent's service only through
    backend/agent_service.py, which names its address once (standards 7, 15)."""
    allowed = ("backend/agent_service.py",)
    assert offending(HTTP_CLIENT, ("backend",), allowed) == []
    assert offending(re.compile(r"UNDERCOVER_AGENT"), ("backend",), allowed) == []


@pytest.mark.parametrize("client", [api, improver_api], ids=lambda m: m.__name__)
def test_agent_api_is_named_after_the_operations(client):
    """Each function in the agent's clients is a backend operation, by name
    (standard 16)."""
    functions = {
        name
        for name, member in inspect.getmembers(client, inspect.isfunction)
        if member.__module__ == client.__name__
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
        "get_configuration",
        "get_version_details",
    }
    assert kept_out <= operation_ids()
    assert not kept_out & set(dir(api))
    reads = re.compile(r"[\"']/api/(evaluations|dispatches|configuration)")
    assert offending(reads, ("agent",), ("agent/service.py",)) == []


def imports(module: str) -> set[str]:
    """The agent's modules a module of the agent imports."""
    tree = ast.parse((ROOT / f"agent/{module}.py").read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "agent":
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "agent."
        ):
            found.add((node.module or "").removeprefix("agent."))
    return found


def test_the_claim_agent_has_no_way_to_the_improvers_operations():
    """The claim agent's client reaches nothing of rounds, improvement, the
    configuration's history, the settings or the evaluations' scores; the claim
    agent's modules never import the improver's client; and the improver
    reaches claim agents only through the function the service hands it."""
    source = (ROOT / "agent/api.py").read_text(encoding="utf-8")
    kept_out = r"/api/(rounds|improvement|configuration|settings|evaluations)"
    assert re.search(kept_out, source) is None
    for module in ("tools", "graph", "harness"):
        assert "improver_api" not in imports(module), module
    assert not {"harness", "dispatcher"} & imports("improver")
