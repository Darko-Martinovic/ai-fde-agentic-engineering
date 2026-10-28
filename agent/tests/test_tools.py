import json

from agent import api, harness
from agent.tests.stub import FREE, decide, stub, tool_call
from agent.tools import CLAIM_TOOLS

TRIP_DELAY = [
    {"description": "Airport hotel", "amount": 245.0, "kind": "hotel", "nights": 1},
    {"description": "Dinner and breakfast", "amount": 95.0, "kind": "expense"},
    {"description": "Taxis", "amount": 80.0, "kind": "expense"},
]
# The model gives every line's nights and hours, 0 where they don't apply
TRIP_DELAY = [{"nights": 0, "hours": 0} | line for line in TRIP_DELAY]


def test_the_claim_agents_tools_are_named_after_operations():
    names = [claim_tool.name for claim_tool in CLAIM_TOOLS]
    assert names == [
        "get_claim",
        "get_policy",
        "get_customer",
        "search_documents",
        "read_section",
        "calculate_payout",
        "decide_claim",
    ]


def test_the_agent_works_out_the_payout_with_the_rules(backend, run, memory_saver):
    llm = stub(
        tool_call(
            "calculate_payout",
            benefit="trip_delay",
            lines=TRIP_DELAY,
            paid_by_others=0,
        ),
        decide("approve", 420.0),
    )
    assert harness.work_claim("CLM-1001", run, FREE, memory_saver, llm).endswith("paid")
    steps = backend.get("/api/claims/CLM-1001/steps").json()
    assert steps[0]["text"].startswith("calculate_payout ")
    worked_out = json.loads(steps[1]["text"])
    assert worked_out["payout"] == 420.0
    assert worked_out["needs_sign_off"] is False


def test_a_copy_reads_as_any_claim(backend, memory_saver):
    """The claim agent works an evaluation's copy without knowing it's one."""
    run = api.create_evaluation("held_out", True, 5)
    copy_id = run["claims"][0]["claim_id"]
    llm = stub(tool_call("get_claim"), decide("decline", 0))
    harness.work_claim(copy_id, run["run_id"], FREE, memory_saver, llm)
    steps = backend.get(f"/api/claims/{copy_id}/steps").json()
    [read] = [s["text"] for s in steps if s["kind"] == "tool_result"][:1]
    assert copy_id in read
    assert "evaluation_id" not in read
    assert "copy_of" not in read
