"""Whether the backend runs on AWS Lambda, and that the backend, which goes to
Lambda alone, imports nothing of the agent's."""

import ast
from pathlib import Path

from backend.lambda_runtime import on_lambda

BACKEND = Path(__file__).parents[1]


def test_on_lambda_is_whether_lambda_named_the_function(monkeypatch):
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    assert not on_lambda()
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "undercover-app")
    assert on_lambda()


def test_the_backend_imports_nothing_of_the_agents():
    for module in BACKEND.rglob("*.py"):
        if "tests" in module.parts:
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"))
        imported = [
            name
            for node in ast.walk(tree)
            for name in (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
        ]
        assert not any(name.split(".")[0] == "agent" for name in imported), module
