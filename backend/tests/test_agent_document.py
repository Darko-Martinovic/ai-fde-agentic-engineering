"""The claim agent's own API document, for the AgentCore Gateway."""

import json
import re

from backend.agent_document import AGENT_OPERATIONS

REFERENCE = re.compile(r'"#/components/schemas/([^"]+)"')

PATH = "/api/agent/openapi.json"


def operations(document):
    return {
        operation["operationId"]: operation
        for methods in document["paths"].values()
        for operation in methods.values()
    }


def test_it_holds_exactly_the_claim_agents_eight_operations(client):
    document = client.get(PATH).json()
    assert set(operations(document)) == {
        "get_claim",
        "get_policy",
        "get_claim_history",
        "search_documents",
        "read_section",
        "calculate_payout",
        "record_decision",
        "pay_claim",
    }
    assert set(AGENT_OPERATIONS) == set(operations(document))


def test_it_names_no_server_and_no_key(client):
    document = client.get(PATH).json()
    assert "servers" not in document
    assert "securitySchemes" not in document["components"]
    for operation in operations(document).values():
        assert "security" not in operation
        assert all(
            parameter["in"] != "header" for parameter in operation.get("parameters", [])
        )


def test_each_operation_keeps_its_docstring_and_the_payment_its_amount(client):
    document = client.get(PATH).json()
    for operation in operations(document).values():
        assert operation["description"]
    payment = operations(document)["pay_claim"]["requestBody"]["content"]
    reference = payment["application/json"]["schema"]["$ref"].split("/")[-1]
    assert set(document["components"]["schemas"][reference]["properties"]) == {"amount"}


def test_every_schema_it_refers_to_is_in_it(client):
    document = client.get(PATH).json()
    schemas = document["components"]["schemas"]
    referred = set(REFERENCE.findall(json.dumps(document)))
    assert referred
    assert referred <= set(schemas)
