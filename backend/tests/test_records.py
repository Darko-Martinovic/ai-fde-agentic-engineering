import pytest


def test_list_claims(client):
    response = client.get("/api/claims")
    assert response.status_code == 200
    claims = response.json()
    assert len(claims) == 25
    assert {c["status"] for c in claims} == {"waiting"}
    assert claims[0] == {
        "claim_id": "CLM-1001",
        "claim_type": "trip_delay",
        "customer_name": "Maya Patel",
        "amount_claimed": 420.0,
        "submitted_on": "2026-06-24",
        "status": "waiting",
        "decision": None,
        "payout": None,
        "paid": None,
    }


def test_get_claim(client):
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "waiting"
    assert claim["story"].startswith("My flight home from Rome")
    assert len(claim["items"]) == 3
    assert len(claim["documents"]) == 4
    assert claim["decisions"] == []
    assert claim["payment"] is None


def test_get_policy(client):
    policy = client.get("/api/policies/POL-2001").json()
    assert policy["plan"]["name"] == "UnderCover Premium"
    assert policy["plan"]["deductible"] == 50.0
    assert policy["add_ons"] == []
    assert policy["deductible_applies_to"] == ["baggage", "emergency_medical"]
    assert policy["trip"]["returns_on"] == "2026-06-18"


def test_get_policy_with_an_add_on(client):
    [add_on] = client.get("/api/policies/POL-2009").json()["add_ons"]
    assert add_on["name"] == "Electronics Plus"
    assert add_on["electronics_per_item_limit"] == 1200.0


def test_get_customer(client):
    customer = client.get("/api/customers/CUS-3001").json()
    assert customer["name"] == "Maya Patel"
    assert [c["claim_id"] for c in customer["previous_claims"]] == ["CLM-0412"]


@pytest.mark.parametrize(
    "path",
    ["/api/claims/CLM-9999", "/api/policies/POL-9999", "/api/customers/CUS-9999"],
)
def test_not_found(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert response.json()["detail"].endswith("9999 not found")


def test_get_policy_wording(client):
    response = client.get("/api/policy-wording")
    assert response.text.startswith("# UnderCover Travel Insurance: Policy Wording")


def test_get_instructions(client):
    response = client.get("/api/instructions")
    assert response.text.startswith("# UnderCover Agent")


def test_list_handlers(client):
    handlers = client.get("/api/handlers").json()
    assert [h["handler_id"] for h in handlers] == ["HND-01", "HND-02", "HND-03"]
    assert handlers[0]["name"] == "Dana Whitfield"


def test_operations_are_documented(client):
    paths = client.get("/openapi.json").json()["paths"]
    operations = [op for methods in paths.values() for op in methods.values()]
    assert {op["operationId"] for op in operations} == {
        "health",
        "list_claims",
        "get_claim",
        "get_policy",
        "get_customer",
        "get_policy_wording",
        "get_instructions",
        "list_handlers",
        "start_claim",
        "record_step",
        "list_steps",
        "decide_claim",
        "pay_claim",
        "sign_off_claim",
        "resolve_referral",
        "get_agent",
        "run_claim",
        "run_queue",
        "stop_agent",
        "get_insights",
    }
    assert all(op["summary"] and op["description"] for op in operations)
