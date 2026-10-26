"""The API rules in docs/TECH_STACK.md, for every UnderCover service: each
operation has an operation id and a one-line docstring, and takes no optional
input, down to the fields of the models inside a request body."""

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel

from agent.service import app as agent_service
from backend.main import app as backend

Schema = dict[str, Any]


def optional_fields(schema: Schema, schemas: dict[str, Schema]) -> list[str]:
    """The optional fields in a request body's schema and the models inside it."""
    if "$ref" in schema:
        return optional_fields(schemas[schema["$ref"].rsplit("/", 1)[1]], schemas)
    if schema.get("type") == "array":
        return optional_fields(schema["items"], schemas)
    nested = [
        found
        for key in ("anyOf", "oneOf", "allOf")
        for part in schema.get(key, [])
        for found in optional_fields(part, schemas)
    ]
    properties: dict[str, Schema] = schema.get("properties", {})
    required = set(schema.get("required", []))
    optional = [
        f"{schema.get('title')}.{name}" for name in properties if name not in required
    ]
    inside = [
        found
        for field in properties.values()
        for found in optional_fields(field, schemas)
    ]
    return nested + optional + inside


def unnamed(app: FastAPI) -> list[str]:
    """The routes without an operation id of their own. FastAPI makes one up for
    the OpenAPI document, so it's the routes that tell."""
    return [
        f"{route.path}: no operation id"
        for route in app.routes
        if isinstance(route, APIRoute) and not route.operation_id
    ]


def broken_rules(app: FastAPI) -> list[str]:
    """What breaks the API rules in an app's routes and OpenAPI document."""
    document = app.openapi()
    schemas = document.get("components", {}).get("schemas", {})
    found = unnamed(app)
    for methods in document["paths"].values():
        for operation in methods.values():
            name = operation["operationId"]
            description = operation.get("description", "")
            if not description or "\n\n" in description:
                found.append(f"{name}: not a one-line docstring")
            found += [
                f"{name}: {parameter['name']} is optional"
                for parameter in operation.get("parameters", [])
                if not parameter.get("required")
            ]
            body = operation.get("requestBody")
            if body and not body.get("required"):
                found.append(f"{name}: its body is optional")
            if body:
                schema = body["content"]["application/json"]["schema"]
                found += [
                    f"{name}: {field} is optional"
                    for field in optional_fields(schema, schemas)
                ]
    return found


@pytest.mark.parametrize("app", [backend, agent_service], ids=["backend", "agent"])
def test_every_operation_keeps_the_api_rules(app):
    assert broken_rules(app) == []


def test_an_optional_field_inside_a_body_breaks_the_rules():
    class Inner(BaseModel):
        note: str = ""

    class Outer(BaseModel):
        inner: list[Inner]

    app = FastAPI()

    @app.post("/api/things", operation_id="add_thing")
    def add_thing(thing: Outer) -> None:
        """Add a thing."""

    assert broken_rules(app) == ["add_thing: Inner.note is optional"]


def test_an_operation_without_an_id_or_with_an_optional_body_breaks_the_rules():
    class Thing(BaseModel):
        name: str

    app = FastAPI()

    @app.post("/api/things")
    def add_thing(thing: Thing | None = None) -> None:
        """Add a thing."""

    assert broken_rules(app) == [
        "/api/things: no operation id",
        "add_thing_api_things_post: its body is optional",
    ]
