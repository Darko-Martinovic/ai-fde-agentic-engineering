"""The claim agent's own API document, for the AgentCore Gateway, which makes a
tool of every operation in a document it's given: the claim agent's eight
operations alone, so the dashboard's routes, the evaluations and the sign-off
stay out of the agent's reach. It's cut from the app's own document, with no
servers, since the deployment adds the app's address, and no security schemes,
so the key the Gateway sends is never an input of a tool."""

import json
import re
from typing import Any

from fastapi import APIRouter, Request

from backend.callers import AGENT_OR_HANDLER

AGENT_OPERATIONS = (
    "get_claim",
    "get_policy",
    "get_claim_history",
    "search_documents",
    "read_section",
    "calculate_payout",
    "record_decision",
    "pay_claim",
)
SCHEMA_REF = re.compile(r'"#/components/schemas/([^"]+)"')

router = APIRouter(prefix="/api/agent")


def schemas_used(found: Any, schemas: dict[str, Any]) -> dict[str, Any]:
    """The schemas a part of the document refers to, and those they refer to."""
    used: dict[str, Any] = {}
    waiting = SCHEMA_REF.findall(json.dumps(found))
    while waiting:
        name = waiting.pop()
        if name not in used:
            used[name] = schemas[name]
            waiting += SCHEMA_REF.findall(json.dumps(schemas[name]))
    return used


def agent_paths(document: dict[str, Any]) -> dict[str, Any]:
    """The paths of the claim agent's operations, each without its security."""
    paths: dict[str, Any] = {}
    for path, methods in document["paths"].items():
        for method, operation in methods.items():
            if operation["operationId"] in AGENT_OPERATIONS:
                kept = {
                    key: value for key, value in operation.items() if key != "security"
                }
                paths.setdefault(path, {})[method] = kept
    return paths


@router.get(
    "/openapi.json", operation_id="get_agent_document", dependencies=[AGENT_OR_HANDLER]
)
def get_agent_document(request: Request) -> dict[str, Any]:
    """Get the API document of the claim agent's operations, for the Gateway."""
    document = request.app.openapi()
    paths = agent_paths(document)
    return {
        "openapi": document["openapi"],
        "info": document["info"],
        "paths": paths,
        "components": {
            "schemas": schemas_used(paths, document["components"]["schemas"])
        },
    }
